import serial
import time

class TECModule:
    def __init__(self, port: str, receiver_id: int, baudrate: int = 9600, timeout: int = 1):
        """
        Initializes the TECModule with the given serial port parameters and receiver ID.
        
        Parameters:
            port (str): The serial port to communicate with the TEC module.
            receiver_id (int): The receiver ID for the TEC module.
            baudrate (int): The baud rate for serial communication. Default is 9600.
            timeout (int): The timeout for serial communication. Default is 1 second.
        """
        self.port = port
        self.receiver_id = receiver_id
        self.baudrate = baudrate
        self.timeout = timeout
        self.initialize_tec()  # Automatically initialize TEC upon instantiation

    def send_ascii_command(self, command: str) -> str:
        """
        Sends an ASCII command to the TEC module and returns the response.

        Parameters:
            command (str): The command string to send.
        
        Returns:
            str: The response from the TEC module.
        """
        with serial.Serial(self.port, self.baudrate, timeout=self.timeout) as ser:
            ser.reset_input_buffer()
            print(f"Sending command: {command.strip()} to {self.port}")
            ser.write(command.encode('ascii'))
            time.sleep(0.5)
            response = ser.read(ser.in_waiting).decode('ascii').strip()
        return response
    
    def initialize_tec(self):
        """
        Initializes the TEC module by sending a series of configuration commands.
        """
        commands = [
            "SDI", "SPF 000", "SIF 000", "SDF 000", "SHC 1000", "SCC 1000", 
            "SMA 6000", "SMI 0", "SAE 0", "SUS 1", "SBM 0,0", "SBM 1,0", 
            "SBM 2,0", "SBM 3,0", "SBM 4,0", "SBM 5,0", "SBM 6,0", "SBM 7,0", 
            "SBE 0", "STS 1", "SAS 0", "SEI 0", "SFS 0", "SIM 0", "SM1 0", 
            "SM2 0", "SM3 6500", "STI 0", "STD 0", "SC0 0", "SEN"
        ]
        
        for command in commands:
            formatted_command = f"{self.receiver_id} {command}"
            response = self.send_ascii_command(formatted_command)
            print(f"Response: {response}")

# Example usage:
if __name__ == "__main__":
    port = "/dev/ttyUSB1"  # Change based on your setup
    tec_module_1 = TECModule(port, receiver_id=1)
    response = tec_module_1.send_ascii_command("SDI\n")
    print(f"Response from TEC module: {response}")
