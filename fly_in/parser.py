import os
import sys
from abc import ABC, abstractmethod
from typing import Any

from .errors import ParserError, SimulationError, ValidationError
from .map_builder import MapBuilder
from .render_map import RenderMap
from .simulation_engine import SimulationEngine


class DataProcessor(ABC):
    def __init__(self) -> None:
        self.data: list[Any] = []
        self.index: int = 0

    @abstractmethod
    def validate(self, data: Any) -> bool:
        pass

    @abstractmethod
    def ingest(self, line_number: int, data: Any) -> None:
        pass


# TODO (not decided): this function is shared between HubProcessor and
# ConnectionProcessor. It therefore accepts both zone keys
# (zone/color/max_drones) and connection keys (max_link_capacity), which
# would wrongly let a "hub:" line accept max_link_capacity=, and a
# "connection:" line accept zone=/color=. Question raised but never
# settled: split into two functions, or keep it merged with a
# context parameter?
def check_metadata(data: str) -> bool:
    list_key: list[str] = ["zone", "color", "max_drones",
                           "max_link_capacity"]
    list_zones: list[str] = ["priority", "blocked", "normal", "restricted"]
    key, value = data.split("=", 1)
    if key not in list_key:
        return False
    if key == "zone":
        if value not in list_zones:
            return False
    elif key == "color":
        if not value.isalpha():
            return False
    elif key == "max_drones":
        if not value.isdigit() or not int(value) > 0:
            return False
    if key == "max_link_capacity":
        if not value.isdigit() or not int(value) > 0:
            return False
    return True


class StreamProcessor:
    def __init__(self) -> None:
        self.processors: list[DataProcessor] = []

    def add_processor(self, processor: DataProcessor) -> None:
        for current_processor in self.processors:
            if type(current_processor) is type(processor):
                return
        self.processors.append(processor)

    def ingest_stream(self, line_number: int, data: Any) -> None:
        for processor in self.processors:
            processor.ingest(line_number, data)


class HubProcessor(DataProcessor):
    def validate(self, data: str) -> bool:
        try:
            kind, value = data.split(":", 1)
            if kind not in ("hub", "start_hub", "end_hub"):
                return False
            parts = value.split()

            if len(parts) < 3:
                raise ValidationError("need at least 3 parts")

            for i in range(1, 3):
                try:
                    int(parts[i])
                except ValueError:
                    raise ValidationError("coordonates must be int")

            for i in range(3, len(parts)):
                if not check_metadata(parts[i].strip("[]")):
                    raise ValidationError(f"Metadata in place {i}"
                                          " is incorrect")

        except ValueError:
            raise ValidationError("Line format is invalid")
        return True

    def ingest(self, line_number: int, data: str) -> None:
        if not self.validate(data):
            return
        self.data.append((line_number, data))


class ConnectionProcessor(DataProcessor):
    def validate(self, data: str) -> bool:
        try:
            kind, value = data.split(":", 1)
            if kind != "connection":
                return False
            parts = value.split()

            if len(parts) < 1:
                raise ValidationError("no parameters to this connection")

            # TODO: does not check if len(parts) > 2 (malformed line with
            # too many elements), nor the shape of the connection name
            # parts[0] (must contain a dash separating two valid zone
            # names)
            if len(parts) == 2:
                if not check_metadata(parts[1].strip("[]")):
                    raise ValidationError("Metadata is incorrect")

        except ValueError:
            raise ValidationError("Line format is invalid")
        return True

    def ingest(self, line_number: int, data: str) -> None:
        if not self.validate(data):
            return
        self.data.append((line_number, data))


class InfoProcessor(DataProcessor):
    def validate(self, data: str) -> bool:
        try:
            key, value = data.split(":", 1)
            value = value.strip()
            if key != "nb_drones":
                return False
            if not value.isdigit() or not int(value) > 0:
                raise ValidationError("Drone number must be a positive int")
        except ValueError:
            raise ValidationError("Line format is invalid")
        return True

    def ingest(self, line_number: int, data: str) -> None:
        if not self.validate(data):
            return
        self.data.append((line_number, data))


def parser_monitor() -> None:
    filename = sys.argv[1]
    parser = StreamProcessor()
    processor_hub = HubProcessor()
    info_process = InfoProcessor()
    connection = ConnectionProcessor()
    errors_parser = ParserError()
    parser.add_processor(processor_hub)
    parser.add_processor(connection)
    parser.add_processor(info_process)
    with open(filename) as f:
        data = f.read().splitlines()
        for line_number, line in enumerate(data, start=1):
            if line.startswith("#"):
                continue
            if not line.strip():
                continue
            try:
                parser.ingest_stream(line_number, line)
            except ValidationError as e:
                errors_parser.add_error(line_number, str(e))

    if errors_parser.errors:
        print(errors_parser.errors)
        return

    builder = MapBuilder()

    for line_number, line in info_process.data:
        try:
            builder.set_drone_number(line)
        except ValidationError as e:
            errors_parser.add_error(line_number, str(e))

    for line_number, line in processor_hub.data:
        try:
            builder.add_hub(line_number, line)
        except ValidationError as e:
            errors_parser.add_error(line_number, str(e))

    for line_number, line in connection.data:
        try:
            builder.add_connection(line_number, line)
        except ValidationError as e:
            errors_parser.add_error(line_number, str(e))

    if errors_parser.errors:
        print(errors_parser.errors)
        return

    try:
        map_info = builder.build()
    except ValidationError as e:
        # TODO: 0 is a "sentinel" line number for lack of a better
        # option, since this error (missing or multiple start/end) is
        # not tied to a single precise line in the file
        errors_parser.add_error(0, str(e))
        print(errors_parser.errors)
        return

    engine = SimulationEngine(map_info)
    renderer = RenderMap(map_info)
    os.makedirs("renders", exist_ok=True)

    def render_turn(sim: SimulationEngine, turn_number: int) -> None:
        renderer.render(
            f"renders/turn_{turn_number}.png",
            drone_positions=sim.current_hub_occupancy(),
            transit_positions=sim.current_transit_occupancy(),
            title=f"Turn {turn_number}",
        )

    try:
        turns = engine.run(on_turn=render_turn)
    except SimulationError as e:
        print(f"Simulation error: {e}")
        return

    for turn_moves in turns:
        print(" ".join(turn_moves))
    print(f"Total turns: {len(turns)}")
    print(f"Renders saved in ./renders/ ({len(turns)} images)")