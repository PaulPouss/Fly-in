from abc import ABC, abstractmethod
from typing import Any
import sys


class ParserError(Exception):
    def __init__(self) -> None:
        super().__init__()
        self.errors: dict[int, list[str]] = {}

    def add_error(self, line: int, error: str) -> None:
        self.errors.setdefault(line, []).append(error)


class ValidationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class DataProcessor(ABC):
    def __init__(self):
        self.data: list[Any] = []
        self.index = 0

    @abstractmethod
    def validate(self, data: Any) -> None:
        pass

    @abstractmethod
    def ingest(self, data: Any) -> None:
        pass


class StreamProcessor():
    def __init__(self):
        self.processors: list[DataProcessor] = []

    def add_processor(self, processor: DataProcessor) -> None:
        for current_processors in self.processors:
            if type(current_processors) is type(processor):
                return
        self.processors.append(processor)

    def ingest_stream(self, data: Any) -> None:
        for processors in self.processors:
            processors.ingest(data)


class HubProcessor(DataProcessor):
    def validate(self, data: str) -> None:
        try:
            kind, value = data.split(":", 1)
            if kind not in ("hub", "start_hub", "end_hub"):
                return
            parts = value.split()

            if len(parts) < 3:
                raise ValidationError("need at least 3 parts")

            for i in range(1, 3):
                try:
                    int(parts[i])
                except ValueError:
                    raise ValidationError("coordonates must be int")

        except ValueError:
            raise ValidationError("Line format is invalid")

    def ingest(self, data: Any) -> None:
        self.validate(data)
        self.data.append(data)


class ConnectionProcessor(DataProcessor):
    def validate(self, data: str) -> None:
        try:
            kind, value = data.split(":", 1)
            if kind != "connection":
                return
            parts = value.split()

            if len(parts) < 1:
                raise ValidationError("no parameters to this connection")

        except ValueError:
            raise ValidationError("Line format is invalid")

    def ingest(self, data: Any) -> None:
        self.validate(data)
        self.data.append(data)


def main() -> None:
    filename = sys.argv[1]
    parser = StreamProcessor()
    processor_hub = HubProcessor()
    connection = ConnectionProcessor()
    errors_parser = ParserError()
    parser.add_processor(processor_hub)
    parser.add_processor(connection)
    with open(filename) as f:
        data = f.read().splitlines()
        for line_number, line in enumerate(data, start=1):
            if not line.strip():
                continue
            try:
                parser.ingest_stream(line)
            except ValidationError as e:
                errors_parser.add_error(line_number, str(e))

    if not errors_parser.errors:
        for processor in parser.processors:
            print(processor.data)
    else:
        print(errors_parser.errors)


if __name__ == "__main__":
    main()
