

class MapConst():
    def add_hub(self, line_number: int, data: str) -> None:
        kind, value = data.split(":", 1)
        parts = value.split()
        name: str = parts[0]
        x: int = int(parts[1])
        y: int = int(parts[2])
        metadata = {}
        if len(parts) > 3:
            parts[3].strip("[]")
            for items in parts[3].split():
                key, value = items.split("=", 1)
                metadata[key] = value

