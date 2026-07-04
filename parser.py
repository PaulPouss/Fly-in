import sys


class drone():
    def waiting_his_turn(self) -> None:
        pass

    def go_on_next(self) -> None:
        pass

    def get_back_on_previous(self) -> None:
        pass


class hub ():
    def __init__(self, name: str, coord_x: int, coord_y: int, color: str,
                 max_drone: int = 1) -> None:
        self.name: str = name
        self.x: int = coord_x
        self.y: int = coord_y
        self.color: str = color
        self.max_drone: int = max_drone


class starting_hub(hub):
    def __init__(self, name: str, coord_x: int, coord_y: int, color: str,
                 max_drone: int = 1):
        super().__init__(name, coord_x, coord_y, color, max_drone)
        self.is_starting: bool = True

    def verif_starting_is_correct(self, map: map_info) -> bool:
        if self.max_drone < map.drone_numbers:
            return False
        else:
            return True


class ending_hub(hub):
    pass


class connection():
    pass


class map_info():
    def __init__(self, drone_number: int, starting_hub: starting_hub, last_hub: ending_hub, list_hub: list[hub], list_connection: list[connection]):
        self.drone_numbers = drone_number
        self.starting_hub: starting_hub = starting_hub
        self.ending_hub: ending_hub = last_hub
        self.hub_list: list[hub] = list_hub
        self.connection_list: list[connection] = list_connection

def parser_monitor():
    filename = sys.argv[1]
    with open(filename) as f:
        data = f.read()()

    print(data)
