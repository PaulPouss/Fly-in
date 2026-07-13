import sys
from typing import Any
from enum import Enum


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


class Hub ():
    def __init__(self, name: str, coord_x: int, coord_y: int, color: str,
                 line_number: int, max_drone: int = 1,
                 role: HubRole = HubRole.NORMAL) -> None:
        self.name: str = name
        self.line_number = line_number
        self.x: int = coord_x
        self.y: int = coord_y
        self.color: str = color
        self.max_drone: int = max_drone
        self.role: HubRole = role
        self.drones_on_hub: int = 0


class NormalHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int, color: str,
                 line_number: int, max_drone: int = 1) -> None:
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone)


class BlockedHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int, color: str,
                 line_number: int, max_drone: int = 1):
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone)
        self.blocked: str = "BLOCKED"


class RestrictedHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int, color: str,
                 line_number: int, max_drone: int = 1):
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone)


class PriotityHub(Hub):
    def __init__(self, name: str, coord_x: int, coord_y: int, color: str,
                 line_number: int, max_drone: int = 1):
        super().__init__(name, coord_x, coord_y, color,
                         line_number, max_drone)


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
