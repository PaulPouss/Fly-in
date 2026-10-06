from .classes import (
    BlockedHub,
    Connection,
    Hub,
    HubRole,
    MapInfo,
    NormalHub,
    PriorityHub,
    RestrictedHub,
)
from .errors import ValidationError


class MapBuilder():
    """Incrementally builds a validated MapInfo from already-validated
    input lines.

    Unlike the parser (which only checks that each line is
    syntactically well-formed), MapBuilder turns those lines into real
    Hub/Connection objects and enforces the semantic rules that need
    the whole map to be checked (duplicate names, duplicate
    connections, unknown zone references). Call add_hub/add_connection
    /set_drone_number for each relevant line, then build() to obtain
    the final MapInfo.
    """

    def __init__(self) -> None:
        """Start with an empty map: no hubs, no connections, and a
        drone count of 0 (expected to be overwritten by
        set_drone_number before build() is called)."""
        self.hubs: dict[str, Hub] = {}
        self.connections: list[Connection] = []
        self.seen_connections: set[frozenset[Hub]] = set()
        self.drone_number: int = 0

    def add_hub(self, line_number: int, data: str) -> None:
        """Parse a validated hub/start_hub/end_hub line, build the
        matching Hub subclass, and store it under its name.

        Args:
            line_number: 1-indexed source line, kept on the Hub for
                later error reporting (e.g. duplicate name messages).
            data: the raw line, e.g. "hub: roof1 3 4 [zone=priority]".

        Raises:
            ValidationError: if a metadata key is unrecognized, or if
                a hub with the same name was already added (its
                original line number is included in the message).
        """
        # Split the line
        kind, value = data.split(":", 1)
        parts = value.split()

        name = parts[0]
        x = int(parts[1])
        y = int(parts[2])

        # Determine the role
        if kind == "start_hub":
            role = HubRole.START
        elif kind == "end_hub":
            role = HubRole.END
        else:
            role = HubRole.NORMAL

        # Default metadata values
        metadata_zone: str = "normal"
        metadata_max_drone: int = 1
        color: str | None = None

        # Read metadata
        for item in parts[3:]:
            key, value_meta = item.strip("[]").split("=", 1)

            if key == "max_drones":
                metadata_max_drone = int(value_meta)
            elif key == "color":
                color = value_meta
            elif key == "zone":
                metadata_zone = value_meta
            else:
                raise ValidationError(f"unknown parameter '{key}'")

        # Build the object
        hub: Hub
        if metadata_zone == "normal":
            hub = NormalHub(name=name,
                            coord_x=x,
                            coord_y=y,
                            color=color,
                            line_number=line_number,
                            max_drone=metadata_max_drone,
                            role=role)

        elif metadata_zone == "restricted":
            hub = RestrictedHub(name=name,
                                coord_x=x,
                                coord_y=y,
                                color=color,
                                line_number=line_number,
                                max_drone=metadata_max_drone,
                                role=role)

        elif metadata_zone == "priority":
            hub = PriorityHub(name=name,
                              coord_x=x,
                              coord_y=y,
                              color=color,
                              line_number=line_number,
                              max_drone=metadata_max_drone,
                              role=role)

        elif metadata_zone == "blocked":
            hub = BlockedHub(name=name,
                             coord_x=x,
                             coord_y=y,
                             color=color,
                             line_number=line_number,
                             max_drone=metadata_max_drone,
                             role=role)

        else:
            raise AssertionError

        existing = self.hubs.get(name)
        if existing is not None:
            raise ValidationError(
                f"Line {line_number}: duplicate hub name '{name}' "
                f"(already defined at line {existing.line_number})"
            )

        self.hubs[name] = hub

    def add_connection(self, line_number: int, data: str) -> None:
        """Parse a validated connection line, look up the two Hub
        instances it references, and store the resulting Connection.

        Args:
            line_number: 1-indexed source line, kept on the
                Connection for later error reporting.
            data: the raw line, e.g. "connection: a-b
                [max_link_capacity=2]".

        Raises:
            ValidationError: if the line is malformed, if either
                referenced hub was never added via add_hub(), or if
                this same pair of hubs was already connected before
                (a-b and b-a count as the same connection).
        """
        # Expected format:
        #   connection: a-b
        #   connection: a-b [max_link_capacity=N]
        parts = data.split()

        if len(parts) < 2:
            raise ValidationError(
                f"Line {line_number}: invalid connection format"
            )

        # Full connection name, e.g. "a-b"
        name = parts[1]

        # Default capacity
        max_link_capacity = 1

        # Read the max_link_capacity option if present
        if len(parts) == 3:
            option = parts[2]
            if not (option.startswith("[max_link_capacity=")
                    and option.endswith("]")):
                raise ValidationError(
                    f"Line {line_number}: invalid connection metadata"
                )
            value = option[len("[max_link_capacity="):-1]
            try:
                max_link_capacity = int(value)
            except ValueError:
                raise ValidationError(
                    f"Line {line_number}: "
                    "max_link_capacity must be an integer"
                )
        elif len(parts) > 3:
            raise ValidationError(
                f"Line {line_number}: invalid connection format"
            )

        # Split the two zone names
        hub_names = name.split("-", 1)
        if len(hub_names) != 2 or not hub_names[0] or not hub_names[1]:
            raise ValidationError(
                f"Line {line_number}: invalid connection name '{name}'"
            )
        first_hub_name, second_hub_name = hub_names

        # Look up the two Hub instances in the already-built dictionary
        first_hub = self.hubs.get(first_hub_name)
        second_hub = self.hubs.get(second_hub_name)

        if first_hub is None:
            raise ValidationError(
                f"Line {line_number}: hub '{first_hub_name}' not found"
            )
        if second_hub is None:
            raise ValidationError(
                f"Line {line_number}: hub '{second_hub_name}' not found"
            )

        connection = Connection(
            name, first_hub, second_hub, line_number, max_link_capacity
        )
        connection_key = frozenset((first_hub, second_hub))

        if connection_key in self.seen_connections:
            raise ValidationError(
                f"Line {line_number}: connection already exists"
            )

        self.seen_connections.add(connection_key)
        self.connections.append(connection)

    def set_drone_number(self, data: str) -> None:
        """Parse the "nb_drones: N" line and store the drone count.

        Args:
            data: the raw line, e.g. "nb_drones: 15".

        Raises:
            ValidationError: if the line does not have exactly two
                space-separated parts, or if the second part is not
                an integer.
        """
        parts = data.split()

        # Expected format:
        # nb_drones: N
        if len(parts) != 2:
            raise ValidationError(
                "Invalid format for drone number"
            )

        try:
            self.drone_number = int(parts[1])
        except ValueError:
            raise ValidationError(
                "Drone number must be an integer"
            )
        # TODO (not decided): does not check that the value is strictly
        # positive (the subject requires it). May already be checked
        # upstream by InfoProcessor.validate(), to be confirmed.

    def build(self) -> MapInfo:
        """Assemble everything collected so far into a MapInfo.

        Returns:
            A MapInfo built from the current drone count, hubs, and
            connections.

        Raises:
            ValidationError: propagated from MapInfo's own
                construction if the map is globally inconsistent
                (e.g. missing or duplicate start_hub/end_hub).
        """
        return MapInfo(
            self.drone_number,
            list(self.hubs.values()),
            self.connections,
        )