

class MapConst():
    def add_hub(self, line_number: int, data: str) -> None:
        kind, value = data.split(":", 1)
        parts = value.split()
        if len(parts) < 4:
            