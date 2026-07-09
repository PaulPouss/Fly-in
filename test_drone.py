from abc import ABC, abstractmethod
from typing import Any

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
        if not data.startswith(("hub:", "start_hub:", "end_hub:")):
            return False
        parts = data.split()
        
        if len(parts) < 3:
            return False
        
        if not parts[2].isdigit() or not parts[3].isdigit():
            return False
        
        return True
    
    def ingest(self, data: Any) -> None:
        if not self.validate(data):
            return
        
        self.data.
