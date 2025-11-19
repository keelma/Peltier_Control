import serial
import time


class TECModule:
    def __init__(self, port: str, receiver_id: int, baudrate: int = 9600, timeout: int = 1):
        """
        Initializes the TECModule with the given serial port parameters and receiver ID.
        
        Parameters:
            port (str): Serial port to communicate with the TEC module.
            receiver_id (int): Receiver ID for the TEC module.
            baudrate (int): Baud rate for serial communication. Default 9600.
            timeout (int): Timeout in seconds for serial communication. Default 1.
        """
        self.port = port
        self.receiver_id = receiver_id
        self.baudrate = baudrate
        self.timeout = timeout

        # Automatically initialize the TEC module
        self.tec_initialisation(self.receiver_id, self.port)

    def logging_data(self, port: str, receiver_id: int,command: str):
        ser = serial.Serial(port, baudrate=self.baudrate, timeout=self.timeout)
        ser.reset_input_buffer()

        formatted_command = f"{receiver_id} {command}"
        print(f"Sending command: {formatted_command.strip()} to {port}")

        ser.write(formatted_command.encode('ascii'))
        response = ser.read(ser.in_waiting).decode('ascii').strip()
        ser.close()

        print(f"Response from TEC controller: {response}")
        return response


    def ascii_communication_protocol(self, port: str, receiver_id: int, command: str) -> str:
        """
        Sends an ASCII command to the TEC module and returns the response.

        Parameters:
            port (str): Serial port to use.
            receiver_id (int): Receiver ID for the TEC module.
            command (str): Command string to send.

        Returns:
            str: Response from the TEC module.
        """
        ser = serial.Serial(port, baudrate=self.baudrate, timeout=self.timeout)
        ser.reset_input_buffer()

        formatted_command = f"{receiver_id} {command}"
        print(f"Sending command: {formatted_command.strip()} to {port}")

        ser.write(formatted_command.encode('ascii'))
        time.sleep(0.1)

        response = ser.read(ser.in_waiting).decode('ascii').strip()
        ser.close()

        if response == "COMMAND ERR" or response == "FORMAT ERR" or response == "NUMBER ERR":
            print(f"Response from TEC controller threw an error: {response}")
            return response, False
        print(f"Response from TEC controller: {response}")
        return response, True

    def tec_initialisation(self, receiver_id: int, port: str):
        """
        Sends TEC initialization ASCII commands formatted with the given receiver ID.
        Each command is sent using the predefined ascii_communication_protocol function.

        Parameters:
            receiver_id (int): The receiver ID for the TEC-Controller.
            port (str): The communication port to use.
        """
        commands = [
            "SDI\n", "SPF 000\n", "SIF 000\n", "SDF 000\n",
            "SHC 1600\n", "SCC 0\n", "SMA 6000\n", "SMI 0\n",
            "SAE 0\n", "SUS 1\n", "SBM 0,0\n", "SBM 1,0\n",
            "SBM 2,0\n", "SBM 3,0\n", "SBM 4,0\n", "SBM 5,0\n",
            "SBM 6,0\n", "SBM 7,0\n", "SBE 0\n", "STS 1\n",
            "SAS 0\n", "SEI 0\n", "SFS 0\n", "SIM 0\n",
            "SM1 0\n", "SM2 0\n", "SM3 6500\n", "STI 0\n",
            "STD 0\n", "SC0 0\n", "SEN\n"
        ]

        for command in commands:
            self.ascii_communication_protocol(port, receiver_id, command)

    def send_ascii_command(self, command: str) -> str:
        """
        Sends a single ASCII command to the TEC module and returns the response.

        Parameters:
            command (str): ASCII command to send.

        Returns:
            str: Response from the TEC module.
        """
        return self.ascii_communication_protocol(self.port, self.receiver_id, command)


# Example usage
if __name__ == "__main__":
    port = "/dev/ttyUSB1"
    tec_module_1 = TECModule(port, receiver_id=1)
    response = tec_module_1.send_ascii_command("SDI\n")
    print(f"Response from TEC module: {response}")
