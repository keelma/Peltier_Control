import sm_tc

class TemperatureSensorReaderTC:
    def __init__(self, board_channel_map: dict[int, list[int]]):
        """
        Initialize the thermocouple reader.

        Parameters:
        - board_channel_map: dict mapping board_id -> list of channels
          Example: { 0: [1, 2, 3], 1: [1, 2] }
        """
        self.board_channel_map = board_channel_map

    def read(self) -> list[float]:
        """
        Read all configured thermocouple sensors and return a list of temperature values
        in the order of board_id -> channels.
        """
        temperatures = []
        board_objects = {}

        for board_id, channels in self.board_channel_map.items():
            if board_id not in board_objects:
                board_objects[board_id] = sm_tc.SMtc(board_id)
            tc = board_objects[board_id]

            for channel in channels:
                try:
                    value = tc.get_temp(channel)
                    temperatures.append(round(value, 3))
                except Exception:
                    temperatures.append(None)  # or float("nan")

        return temperatures
