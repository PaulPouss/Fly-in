from .classes import NormalHub, PriorityHub, RestrictedHub, BlockedHub
from .classes import HubRole, Hub


class MapBuilder():
    def __init__(self):
        self.hubs: dict[str, Hub] = {}

    def add_hub(self, line_number: int, data: str) -> None:
        # Découpage de la ligne
        kind, value = data.split(":", 1)
        parts = value.split()

        name = parts[0]
        x = int(parts[1])
        y = int(parts[2])

        # Détermination du rôle
        if kind == "start_hub":
            role = HubRole.START
        elif kind == "end_hub":
            role = HubRole.END
        else:
            role = HubRole.NORMAL

        # Valeurs par défaut des métadonnées
        metadata_zone: str = "normal"
        metadata_max_drone: int = 1
        color: str | None = None

        # Lecture des métadonnées
        for item in parts[3:]:
            key, value_meta = item.strip("[]").split("=", 1)

            if key == "max_drones":
                metadata_max_drone = int(value_meta)
            elif key == "color":
                color = value_meta
            else:
                metadata_zone = value_meta

        # Construction de l'objet
        if metadata_zone == "normal":
            hub = NormalHub(name=name,
                            coord_x=x,
                            coord_y=y,
                            color=color,
                            line_number=line_number,
                            max_drone=metadata_max_drone,
                            role=role,)
        elif metadata_zone == "restricted":
            hub = RestrictedHub(name=name,
                                coord_x=x,
                                coord_y=y,
                                color=color,
                                line_number=line_number,
                                max_drone=metadata_max_drone,
                                role=role,)

        self.hubs[name] = hub
