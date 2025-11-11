import librtd

class TemperatureSensorReaderRTD:
    def __init__(self, board_channel_map: dict[int, list[int]]):
        """
        Parameters:
        - board_channel_map: dict mapping board_id -> list of channels
          Example: { 0: [1, 2, 3], 1: [1, 2, 3, 4] }
        """
        self.board_channel_map = board_channel_map

    def read(self) -> list[float]:
        """
        Read all configured RTD sensors and return a list of temperature values
        in the order of board_id -> channels.
        """
        temperatures = []
        for board_id, channels in self.board_channel_map.items():
            for channel in channels:
                try:
                    value = librtd.get(board_id, channel)
                    temperatures.append(round(value, 3))
                except Exception:
                    temperatures.append(None)  # or float("nan")
        return temperatures
