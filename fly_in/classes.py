from abc import ABC, abstractmethod
from enum import Enum

from .errors import ValidationError


class HubRole(Enum):
    START = "start"
    END = "end"
    NORMAL = "normal"


class Drone():
    def __init__(self, drone_id: int) -> None:
        self.status: str = "waiting"
        # TODO (not decided): status stays a free str for now.
        # Could be consistent with HubRole -> a DroneStatus(Enum) would
        # be safer, never settled with the user.
        self.id: int = drone_id
        self.current_hub: "Hub | None" = None
        self.path: list["Hub"] = []
        self.path_index: int = 0
        # Number of consecutive turns without progress; used by the
        # SimulationEngine to trigger a targeted replanning
        # (hybrid threshold discussed: per-drone counter + global deadlock)
        self.stuck_turns: int = 0

    def waiting_his_turn(self) -> None:
        """Put the drone in waiting state."""
        self.status = "waiting"
        self.stuck_turns += 1

    def go_on_next(self) -> None:
        """Move the drone to the next hub in its path.

        This is meant to be called by the SimulationEngine only, once a
        move has already been validated against capacity constraints for
        the whole turn -- Drone itself never decides to move on its own.
        """
        self.path_index += 1
        self.current_hub = self.path[self.path_index]
        self.stuck_turns = 0
        if self.path_index >= len(self.path) - 1:
            self.status = "finished"
        else:
            self.status = "moving"


class Hub(ABC):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None, line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL) -> None:
        self.name: str = name
        self.line_number: int = line_number
        self.x: int = coord_x
        self.y: int = coord_y
        self.color: str | None = color
        self.max_drone: int = max_drone
        self.role: HubRole = role
        self.drones_on_hub: int = 0
        # TODO: 1000000 is a sentinel value discussed but never finally
        # settled (alternative: float('inf') or a dedicated method)
        if self.role != HubRole.NORMAL:
            self.max_drone = 1000000

    @abstractmethod
    def movement_cost(self) -> int | None:
        pass

    def is_priority(self) -> bool:
        return False


class NormalHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None, line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL) -> None:
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone, role)

    def movement_cost(self) -> int:
        return 1


class BlockedHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None, line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL) -> None:
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone, role)

    def movement_cost(self) -> None:
        return None


class RestrictedHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None, line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL) -> None:
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone, role)

    def movement_cost(self) -> int:
        return 2


class PriorityHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None, line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL) -> None:
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone, role)

    def movement_cost(self) -> int:
        return 1

    def is_priority(self) -> bool:
        return True


class Connection():
    def __init__(self, name: str, first_hub: Hub, second_hub: Hub,
                 line_number: int, max_link_capacity: int = 1) -> None:
        self.name: str = name
        self.line_number: int = line_number
        self.first_hub: Hub = first_hub
        self.second_hub: Hub = second_hub
        self.current_occupation: int = 0
        self.max_link_capacity: int = max_link_capacity


class MapInfo():
    def __init__(self, drone_number: int,
                 list_hub: list[Hub],
                 list_connection: list[Connection]) -> None:
        self.drone_numbers: int = drone_number
        self.hub_list: list[Hub] = list_hub
        self.connection_list: list[Connection] = list_connection
        self.validate()

    def validate(self) -> None:
        self._check_role_count(HubRole.START, "start_hub")
        self._check_role_count(HubRole.END, "end_hub")

    def _check_role_count(self, role: HubRole, label: str) -> None:
        matching = [hub for hub in self.hub_list if hub.role == role]
        if len(matching) == 0:
            raise ValidationError(f"no {label} defined in the map")
        if len(matching) > 1:
            lines = ", ".join(str(hub.line_number) for hub in matching)
            raise ValidationError(
                f"multiple {label} defined at lines {lines}"
            )
        # TODO: name uniqueness and duplicate connections are already
        # guaranteed upstream by MapBuilder (add_hub/add_connection) ->
        # not revalidated here (no defense in depth for now)