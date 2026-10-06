*This project has been created as part of the 42 curriculum by ppousser42.*

# Fly-in

## Description

Fly-in is a Python simulation that routes a fleet of autonomous drones
from a start zone to an end zone across a network of connected zones,
in the fewest possible simulation turns. The network is described in a
text file (zones with their coordinates and type, connections between
them), and the program must respect movement costs, zone/connection
capacity limits, and the special two-turn commitment required to enter
a restricted zone, while scheduling as many drones as possible to move
simultaneously.

The project is split into four concerns: parsing and validating the
input file, building a typed, internally-consistent map model,
simulating the fleet turn by turn, and rendering the map (and the
drones on it) to an image at every turn.

## Instructions

Requirements: Python 3.10+. A virtual environment is recommended (see
III.3 of the subject) but not required.

```bash
make install        # installs matplotlib, flake8, mypy
make run             # runs the simulation on test_easy.txt
make run ARGS=path/to/map.txt   # runs it on a different map
make debug           # same as `run`, under pdb
make lint            # flake8 + mypy (subject's required flags)
make lint-strict      # flake8 + mypy --strict
make clean           # removes __pycache__ and .mypy_cache
```

Running the simulation prints the turn-by-turn move log to stdout
(`D<ID>-<zone>` / `D<ID>-<connection>`, one line per turn, as required
by the subject) followed by the total turn count, and saves one PNG
per turn under `./renders/` (`turn_1.png`, `turn_2.png`, ...) showing
the map and where every drone is at that point in the simulation.

`test_render.py` is a separate manual script (not graded, see III.3)
that only renders the static map layout for a couple of sample files,
without running a simulation -- useful for quickly checking a new map
file visually before simulating it.

## Project structure

```
main.py                 entry point: python3 main.py <map_file>
fly_in/
    errors.py            shared exceptions (ParserError, ValidationError,
                          SimulationError)
    classes.py            the data model: HubRole, Hub (+ its four
                          subclasses), Connection, Drone, MapInfo
    parser.py              reads the input file, validates it line by
                          line, orchestrates the whole pipeline
    map_builder.py          turns validated lines into real Hub/
                          Connection objects and a validated MapInfo
    simulation_engine.py     the turn-by-turn simulation itself
    render_map.py           draws a map (and optionally the drones on
                          it) to a PNG
test_easy.txt, test_hard.txt   sample maps used for manual testing
```

## Algorithm choices and implementation strategy

**Parsing.** Each line type (`hub`/`start_hub`/`end_hub`, `connection`,
`nb_drones`) has its own validator, and every line in the file is
checked before anything is built, with every problem found collected
into a single report (line number + cause) instead of stopping at the
first error.

**Modeling.** `Hub` is an abstract base class with four polymorphic
subclasses (`NormalHub`, `BlockedHub`, `RestrictedHub`,
`PriorityHub`), each implementing its own `movement_cost()` rather
than branching on a zone-type string. A hub's *role* (start/end/
normal) is a separate `HubRole` enum, orthogonal to its zone type --
combining the two as a single inheritance tree would otherwise force
an impossible class for, say, a restricted start zone. `MapBuilder`
turns validated lines into these objects and `MapInfo` itself refuses
to exist in an inconsistent state (duplicate names, missing or
duplicate start/end) by validating itself at construction time.

**Pathfinding.** A standard Dijkstra, weighted by each hub's
`movement_cost()`. Priority zones are preferred only as a tie-break
between paths of otherwise equal cost, not as an active cost discount
-- a priority zone is never chosen at the expense of a longer route,
which is one reasonable reading of the subject's "should be
prioritized in pathfinding" without it overriding the actual
shortest-path cost.

**Distributing drones across several paths.** A handful of distinct
start-to-goal routes are found by searching once, then temporarily
penalizing the hubs used by the path just found before searching
again, favoring route diversity instead of funneling every drone down
the single globally shortest path. Drones are then distributed across
the paths found, weighted by each path's bottleneck capacity (its
smallest `max_drone` / `max_link_capacity` along the way).

**Turn resolution and capacity.** Every turn, each active drone's
desired next hop is collected first; capacity is then resolved per
destination hub/connection. A move's bookkeeping -- decrementing the
drone's old hub and incrementing the new one -- only ever happens
atomically, at the exact moment that specific move is approved, never
speculatively for a move that might still be denied. This is what
guarantees a hub's or connection's occupancy can never exceed its
declared capacity, even under contention.

**Restricted zones.** Entering one is a two-turn commitment: the
destination slot and the connection are reserved the turn the drone
leaves, and the drone arrives automatically the turn after, with no
way to wait mid-transit -- matching the subject's rule that a drone
"cannot wait on the connection for an empty space in the destination
zone." The connection is only released once the drone actually
arrives.

**Replanning and deadlocks.** A drone that stays blocked for several
consecutive turns (not just a normal queueing wait behind a full hub)
triggers a fresh Dijkstra search from its current position rather than
waiting indefinitely. If an entire turn goes by with no drone able to
move at all, the simulation stops with a clear error instead of
looping forever.

**Complexity.** Resolving a single turn is roughly linear in the
number of active drones and connections. Pathfinding is a standard
Dijkstra (`O((H + C) log H)` per search), run a bounded number of
times at startup to distribute drones across paths, and occasionally
again only for a drone that gets stuck -- not on every turn for every
drone.

## Visual representation

`RenderMap` draws one PNG per simulation turn with matplotlib,
plotting every hub directly at its real `(x, y)` coordinates from the
input file -- no separate graph-layout algorithm is needed since the
subject already provides positions. Each render shows:

- every hub as a marker shaped by its role (square for start, star for
  end, circle otherwise) and colored by its `color=` metadata, falling
  back to a type-based color for normal/priority/restricted/blocked
  zones when none is given (and whenever the given color isn't one
  matplotlib actually recognizes);
- connections as lines, annotated with their capacity whenever it is
  greater than 1;
- drones currently on a hub, shown as a count next to it;
- drones in forced transit toward a restricted zone, shown as a
  separate marker on the connection itself rather than on either hub,
  since that's literally where the subject says they are during those
  two turns.

Marker size, font size, and label placement all scale with how dense
the map actually is (the smallest distance between any two hubs), and
each label is pushed away from that hub's nearest neighbor rather than
alternated arbitrarily -- so a cramped map with many hubs close
together stays readable instead of overlapping, without needing a
different renderer for small and large maps. Together, this turns an
otherwise opaque turn-by-turn text log into something that can be
scanned at a glance to see where congestion is building up and why a
particular route was chosen.

## Resources

- The project subject itself (*Fly-in*, version 1.5)
- Dijkstra's algorithm (standard reference, e.g. any introductory
  algorithms textbook or https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)
- Python standard library docs for `heapq`, `enum`, `abc`, and
  `typing`
- [Matplotlib documentation](https://matplotlib.org/stable/) for
  `pyplot`, `Axes`, and color handling (`matplotlib.colors`)

**AI usage.** Claude (Anthropic) was used throughout development as a
design-and-review collaborator, not as a code generator working
unsupervised.

Every change was tested against the project's own sample maps before
being kept.