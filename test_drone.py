from abc import ABC, abstractmethod
from typing import Any
import sys

class DataProcessor(ABC):
    def __init__(self):
        self.data: list[Any] = []
        self.index = 0

    def output(self) -> tuple[int, str]:
        if self.index < len(self.data):
            self.index += 1
            return (self.index - 1, self.data[self.index - 1])
        else:
            raise IndexError

    @abstractmethod
    def validate(self, data: Any) -> bool:
        pass

    @abstractmethod
    def ingest(self, data: Any) -> None:
        pass


class HubProcessor(DataProcessor):
    def validate(self, data: str) -> bool:
        try:
            kind, value = data.split(":", 1)
            if kind not in ("hub", "start_hub", "end_hub"):
                return False
            parts = value.split()

            if len(parts) < 3:
                return False

            if not parts[1].isdigit() or not parts[2].isdigit():
                return False

        except ValueError:
            return False
        return True

    def ingest(self, data: Any) -> None:
        if not self.validate(data):
            return

        self.data.append(data)


def main() -> None:
    filename = sys.argv[1]
    processor = HubProcessor()
    with open(filename) as f:
        data = f.read().splitlines()
        for lines in data:
            processor.ingest(lines)
    print(processor.data)


if __name__ == "__main__":
    main()
