from typing import Any
from enum import Enum
from abc import ABC, abstractmethod


class HubRole(Enum):
    START = "start"
    END = "end"
    NORMAL = "normal"


class Drone():
    def __init__(self, drone_id: int):
        self.status: str = "waiting"
        self.id: int = drone_id
        self.current_hub: Hub | None = None
        self.path: list[Any] = []
        self.path_index = 0

    def waiting_his_turn(self) -> None:
        pass

    def go_on_next(self) -> None:
        pass

    def get_back_on_previous(self) -> None:
        pass


class Hub(ABC):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None,
                 line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL) -> None:
        self.name: str = name
        self.line_number = line_number
        self.x: int = coord_x
        self.y: int = coord_y
        self.color: str | None = color
        self.max_drone: int = max_drone
        self.role: HubRole = role
        self.drones_on_hub: int = 0
        if self.role != HubRole.NORMAL:
            self.max_drone = 1000000

    @abstractmethod
    def movement_cost(self) -> int | None:
        pass

    def is_priority(self) -> bool:
        return False


class NormalHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None,
                 line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL) -> None:
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone, role)

    def movement_cost(self) -> int:
        return 1


class BlockedHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None,
                 line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL):
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone, role)

    def movement_cost(self) -> None:
        return None


class RestrictedHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None,
                 line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL):
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone, role)

    def movement_cost(self) -> int:
        return 2


class PriorityHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int,
                 color: str | None,
                 line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL):
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone, role)

    def movement_cost(self) -> int:
        return 1

    def is_priority(self) -> bool:
        return True


class Connection():
    def __init__(self, name: str, first_hub: Hub, second_hub: Hub,
                 line_number: int, max_link_capacity: int = 1):
        self.name = name
        self.line_number = line_number
        self.first_hub = first_hub
        self.second_hub = second_hub
        self.current_occupation: int = 0
        self.max_link_capacity = max_link_capacity


class MapInfo():
    def __init__(self, drone_number: int,
                 list_hub: list[Hub], list_connection: list[Connection]):
        self.drone_numbers = drone_number
        self.hub_list: list[Hub] = list_hub
        self.connection_list: list[Connection] = list_connection
