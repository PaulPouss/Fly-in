import heapq
from itertools import count
from typing import Callable

from .classes import Connection, Drone, Hub, HubRole, MapInfo
from .errors import SimulationError

# TODO (not decided with the user): threshold of consecutive stuck turns
# before triggering a targeted replanning for a drone. Value chosen
# arbitrarily, never precisely discussed.
STUCK_TURNS_THRESHOLD = 2


class SimulationEngine():
    def __init__(self, map_info: MapInfo) -> None:
        self.map_info: MapInfo = map_info
        self.start: Hub = self._find_unique_role(HubRole.START)
        self.end: Hub = self._find_unique_role(HubRole.END)
        self.adjacency: dict[Hub, list[tuple[Connection, Hub]]] = (
            self._build_adjacency()
        )
        self.drones: list[Drone] = self._create_drones()
        self.turns_log: list[list[str]] = []
        # Drones currently in forced transit (2 turns) toward a
        # restricted zone: hub -> destination already reserved, waiting
        # for automatic arrival next turn.
        self._in_transit: dict[Drone, tuple[Connection, Hub]] = {}
        self._reserved_hub_slots: dict[Hub, int] = {}
        self.turn_number = 0

    # ------------------------------------------------------------------
    # Construction / initialization
    # ------------------------------------------------------------------

    def _find_unique_role(self, role: HubRole) -> Hub:
        for hub in self.map_info.hub_list:
            if hub.role == role:
                return hub
        # Should never happen: already guaranteed by MapInfo.validate()
        raise SimulationError(f"no hub found with role {role}")

    def _build_adjacency(self) -> dict[Hub, list[tuple[Connection, Hub]]]:
        adjacency: dict[Hub, list[tuple[Connection, Hub]]] = {
            hub: [] for hub in self.map_info.hub_list
        }
        for connection in self.map_info.connection_list:
            a, b = connection.first_hub, connection.second_hub
            adjacency[a].append((connection, b))
            adjacency[b].append((connection, a))
        return adjacency

    def _create_drones(self) -> list[Drone]:
        drones = [Drone(i) for i in range(self.map_info.drone_numbers)]
        paths = self._compute_distributed_paths()
        # Weighted round-robin distribution based on the bottleneck
        # capacity of each path found (see _compute_distributed_paths).
        # TODO (heuristic not validated in detail with the user): a
        # strictly proportional distribution would be more rigorous
        # than a simplified weighted round-robin.
        weighted_paths: list[list[Hub]] = []
        for path, weight in paths:
            weighted_paths.extend([path] * max(weight, 1))

        if not weighted_paths:
            raise SimulationError("no path found from start to end")

        for i, drone in enumerate(drones):
            path = weighted_paths[i % len(weighted_paths)]
            drone.path = path
            drone.path_index = 0
            drone.current_hub = path[0]
        return drones

    # ------------------------------------------------------------------
    # Pathfinding
    # ------------------------------------------------------------------
    def _path_score(self, path: list[Hub]) -> tuple[int, int]:
        total_cost = 0
        priority_hops = 0

        for hub in path[1:]:
            cost = hub.movement_cost()

            if cost is None:
                raise SimulationError("path contains a blocked hub")

            total_cost += cost

            if hub.is_priority():
                priority_hops += 1

        return total_cost, -priority_hops

    def _dijkstra(
        self,
        start: Hub,
        end: Hub,
        blocked_hubs: set[Hub] | None = None,
        blocked_connections: set[frozenset[Hub]] | None = None,
    ) -> list[Hub] | None:
        """Shortest path by movement_cost(), tie-broken toward priority
        zones (more priority hops preferred at equal cost)."""
        blocked_hubs = blocked_hubs or set()
        blocked_connections = blocked_connections or set()
        counter = count()
        # (total_cost, -priority_hops, tie_breaker, hub)
        frontier: list[tuple[int, int, int, Hub]] = [
            (0, 0, next(counter), start)
        ]
        best_cost: dict[Hub, tuple[int, int]] = {start: (0, 0)}
        previous: dict[Hub, Hub] = {}

        while frontier:
            cost, neg_priority, _, current = heapq.heappop(frontier)
            if current == end:
                return self._reconstruct_path(previous, start, end)
            if (cost, neg_priority) > best_cost.get(
                current, (float("inf"), float("inf"))
            ):
                continue
            for connection, neighbor in self.adjacency[current]:
                if neighbor in blocked_hubs:
                    continue

                if frozenset((current, neighbor)) in blocked_connections:
                    continue

                step_cost = neighbor.movement_cost()
                if step_cost is None:
                    continue  # blocked zone, impassable

                new_cost = cost + step_cost
                new_neg_priority = neg_priority - (
                    1 if neighbor.is_priority() else 0
                )
                candidate = (new_cost, new_neg_priority)
                if candidate < best_cost.get(
                    neighbor, (float("inf"), float("inf"))
                ):
                    best_cost[neighbor] = candidate
                    previous[neighbor] = current
                    heapq.heappush(
                        frontier,
                        (new_cost, new_neg_priority, next(counter),
                         neighbor),
                    )
        return None

    def _reconstruct_path(
        self, previous: dict[Hub, Hub], start: Hub, end: Hub
    ) -> list[Hub]:
        path = [end]
        while path[-1] != start:
            path.append(previous[path[-1]])
        path.reverse()
        return path

    def _path_bottleneck(self, path: list[Hub]) -> int:
        """Bottleneck capacity of a path: the smallest
        max_drone/max_link_capacity encountered along its route."""
        bottleneck = min(
            (hub.max_drone for hub in path[1:-1]), default=10**9
        )
        for a, b in zip(path, path[1:]):
            for connection, neighbor in self.adjacency[a]:
                if neighbor == b:
                    bottleneck = min(bottleneck, connection.max_link_capacity)
                    break
        return max(bottleneck, 1)

    def _compute_distributed_paths(self) -> list[tuple[list[Hub], int]]:
        """Find up to K distinct shortest paths using Yen's algorithm."""

        max_paths = 4

        first_path = self._dijkstra(self.start, self.end)

        if first_path is None:
            return []

        accepted_paths: list[list[Hub]] = [first_path]

        # Candidate paths ordered by their Dijkstra score.
        candidates: list[tuple[int, int, int, tuple[Hub, ...]]] = []
        candidate_set: set[tuple[Hub, ...]] = set()

        counter = count()

        for _ in range(max_paths - 1):
            previous_path = accepted_paths[-1]

            for i in range(len(previous_path) - 1):
                root_path = previous_path[:i + 1]
                spur_hub = root_path[-1]

                blocked_hubs = set(root_path[:-1])
                blocked_connections: set[frozenset[Hub]] = set()

                # Remove edges that would reproduce an already
                # accepted path sharing the same root.
                for path in accepted_paths:
                    if (
                        len(path) > i + 1
                        and path[:i + 1] == root_path
                    ):
                        blocked_connections.add(
                            frozenset((path[i], path[i + 1]))
                        )

                spur_path = self._dijkstra(
                    spur_hub,
                    self.end,
                    blocked_hubs=blocked_hubs,
                    blocked_connections=blocked_connections,
                )

                if spur_path is None:
                    continue

                total_path = root_path[:-1] + spur_path
                candidate = tuple(total_path)

                if (
                    candidate in candidate_set
                    or total_path in accepted_paths
                ):
                    continue

                cost, neg_priority = self._path_score(total_path)

                heapq.heappush(
                    candidates,
                    (
                        cost,
                        neg_priority,
                        next(counter),
                        candidate,
                    ),
                )

                candidate_set.add(candidate)

            if not candidates:
                break

            _, _, _, best_candidate = heapq.heappop(candidates)

            accepted_paths.append(list(best_candidate))

        return [
            (path, self._path_bottleneck(path))
            for path in accepted_paths
        ]
    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(
        self,
        on_turn: "Callable[[SimulationEngine, int], None] | None" = None,
    ) -> list[list[str]]:
        while True:
            turn_moves = self.step()

            if turn_moves is None:
                break

            if on_turn is not None:
                on_turn(self, self.turn_number)

        return self.turns_log

    def _run_one_turn(self, active: list[Drone]) -> bool:
        turn_moves: list[str] = []
        any_move = False

        # 1. Drones already in forced transit arrive automatically.
        for drone in list(self._in_transit.keys()):
            connection, destination = self._in_transit.pop(drone)

            # Release the reserved slot.
            reserved = self._reserved_hub_slots.get(destination, 0)

            if reserved <= 0:
                raise SimulationError(
                    f"missing hub reservation for {destination.name}"
                )

            if reserved == 1:
                del self._reserved_hub_slots[destination]
            else:
                self._reserved_hub_slots[destination] -= 1

            # Convert reservation into physical occupancy.
            drone.go_on_next()
            destination.drones_on_hub += 1

            connection.current_occupation = max(
                0, connection.current_occupation - 1
            )

            turn_moves.append(f"D{drone.id}-{destination.name}")
            any_move = True

        # Drones that just arrived (status "finished") must no longer
        # be considered for the rest of this turn.
        still_active = [d for d in active if d.status != "finished"]

        # 2. Normal move requests / restricted zone commitments.
        requests: dict[Hub, list[Drone]] = {}
        commit_requests: dict[Hub, list[Drone]] = {}

        for drone in still_active:
            if drone in self._in_transit or drone.status == "finished":
                continue
            next_hub = drone.path[drone.path_index + 1]
            cost = next_hub.movement_cost()
            if cost is None:
                # Should never happen: pathfinding never crosses a
                # BlockedHub.
                raise SimulationError("path goes through a blocked hub")
            if cost >= 2:
                commit_requests.setdefault(next_hub, []).append(drone)
            else:
                requests.setdefault(next_hub, []).append(drone)

        # 3. Resolve normal moves (arbitration by increasing id in case
        # of conflict -- TODO: arbitrary strategy, never discussed in
        # detail).
        #
        # IMPORTANT: a drone's current hub is only decremented at the
        # exact moment its move is approved here -- never earlier,
        # speculatively, for every drone that merely *requests* a
        # move. An earlier version decremented the source hub for
        # every requester up front (assuming they would all leave),
        # then only re-incremented the destination for the ones that
        # actually succeeded. Drones that lost the arbitration below
        # and had to wait never got their old hub's count restored,
        # so occupancy drifted lower than reality turn after turn --
        # eventually letting more drones into a hub than its
        # max_drone allowed. Keeping the source-hub decrement and the
        # destination-hub increment together, only on approval, is
        # what guarantees drones_on_hub can never overflow.
        #
        # TODO (trade-off, not discussed with the user): because of
        # this, a hub cannot accept an incoming drone this same turn
        # by counting on one of its current occupants leaving this
        # same turn (VII.3's "moving out frees capacity for that same
        # turn") unless that occupant's own move happens to be
        # resolved earlier in this loop. Safety (never exceeding
        # max_drone) was prioritized over that same-turn optimization.
        for hub, drones in requests.items():
            drones_sorted = sorted(drones, key=lambda d: d.id)
            for drone in drones_sorted:
                connection = self._connection_between(
                    drone.current_hub, hub
                )
                available = (
                                hub.max_drone
                                - hub.drones_on_hub
                                - self._reserved_hub_slots.get(hub, 0)
                            )
                if (available > 0
                        and connection.current_occupation
                        < connection.max_link_capacity):
                    connection.current_occupation += 1
                    old_hub = drone.current_hub
                    drone.go_on_next()
                    if old_hub is not None:
                        old_hub.drones_on_hub = max(
                            0, old_hub.drones_on_hub - 1
                        )
                    hub.drones_on_hub += 1
                    connection.current_occupation -= 1
                    turn_moves.append(f"D{drone.id}-{hub.name}")
                    any_move = True
                else:
                    drone.waiting_his_turn()

        # 4. Resolve commitments toward a restricted zone (2 turns):
        # the slot is reserved immediately for next turn. Same
        # atomic-decrement-on-approval rule as above.
        for hub, drones in commit_requests.items():
            drones_sorted = sorted(drones, key=lambda d: d.id)
            for drone in drones_sorted:
                connection = self._connection_between(
                    drone.current_hub, hub
                )
                available = (
                            hub.max_drone
                            - hub.drones_on_hub
                            - self._reserved_hub_slots.get(hub, 0)
                        )
                if (available > 0
                        and connection.current_occupation
                        < connection.max_link_capacity):

                    connection.current_occupation += 1

                    old_hub = drone.current_hub

                    if old_hub is not None:
                        old_hub.drones_on_hub = max(
                            0, old_hub.drones_on_hub - 1
                        )

                    # Reserve a slot in the destination hub.
                    self._reserved_hub_slots[hub] = (
                        self._reserved_hub_slots.get(hub, 0) + 1
                    )

                    self._in_transit[drone] = (connection, hub)

                    drone.status = "moving"
                    drone.stuck_turns = 0

                    turn_moves.append(f"D{drone.id}-{connection.name}")
                    any_move = True

                else:
                    drone.waiting_his_turn()
                    self._maybe_replan(drone)
        self.turns_log.append(turn_moves)
        return any_move

    def current_hub_occupancy(self) -> dict[str, int]:
        """Number of drones currently physically sitting on each hub
        (excludes drones in forced transit on a connection)."""
        occupancy: dict[str, int] = {}
        for drone in self.drones:
            if drone.status == "finished" or drone in self._in_transit:
                continue
            if drone.current_hub is None:
                continue
            occupancy[drone.current_hub.name] = (
                occupancy.get(drone.current_hub.name, 0) + 1
            )
        return occupancy

    def current_transit_occupancy(self) -> dict[str, int]:
        """Number of drones currently in forced transit on each
        connection (toward a restricted zone)."""
        occupancy: dict[str, int] = {}
        for connection, _ in self._in_transit.values():
            occupancy[connection.name] = occupancy.get(
                connection.name, 0
            ) + 1
        return occupancy

    def _connection_between(self, a: Hub | None, b: Hub) -> Connection:
        if a is None:
            raise SimulationError("drone has no current hub")
        for connection, neighbor in self.adjacency[a]:
            if neighbor == b:
                return connection
        raise SimulationError(f"no connection between {a.name} and {b.name}")

    def _maybe_replan(self, drone: Drone) -> None:
        if drone.stuck_turns < STUCK_TURNS_THRESHOLD:
            return
        if drone.current_hub is None:
            return
        new_path = self._dijkstra(drone.current_hub, self.end)
        if new_path is None:
            return
        drone.path = new_path
        drone.path_index = 0
        drone.stuck_turns = 0

    def step(self) -> list[str] | None:
        """Execute exactly one simulation turn.

        Returns the moves made during this turn, or None if finished.
        """
        active = [d for d in self.drones if d.status != "finished"]

        if not active:
            return None

        self.turn_number += 1

        moved = self._run_one_turn(active)

        if not moved:
            raise SimulationError(
                "deadlock detected: no drone could move this turn"
            )

        return self.turns_log[-1]
