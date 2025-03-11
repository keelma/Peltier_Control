import serial
import time

def ascii_communication_protocol(port: str, command: str):
    ser = serial.Serial(port, baudrate = 9600, timeout=1)

    # Flush input to clear any existing data
    ser.reset_input_buffer()

    print(f"Sending command: {command.strip()} to {port}")

    ser.write(command.encode('ascii'))

    time.sleep(0.5)

    response = ser.read(ser.in_waiting).decode('ascii').strip()

    ser.close()

    return response
    
def tec_initalisation(receiver_id, port): # Initalises the TEC-Module by eg. disabling PID Control and the sensors
    """
    Sends TEC Initalisation ASCII commands formatted with the given receiver ID.
    Each command is sent using the predefined ascii_communication function.

    Parameters:
        receiver_id (int): The receiver ID for the TEC-Controller.
        port (str): The communication port to use.
    """
    commands = [
        "SDI",  # Disable TEC-Controller
        "SPF 000",  # Set proportional factor to 0
        "SIF 000",  # Set integral factor to 0
        "SDF 000",  # Set differential factor to 0
        "SHC 1000",  # Set heating current limit to 10.00 A
        "SCC 1000",  # Set cooling current limit to 10.00 A
        "SMA 6000",  # Set maximum temperature to 60.00°C
        "SMI 0",  # Set minimum temperature to 0.00°C
        "SAE 0",  # Disable automatic enabling
        "SUS 1",  # Use temperature sensor 1 for regulation
        "SBM 0,0",  # WE DONT KNOW: Set auxiliary I/O 1 to inactive
        "SBM 1,0",  # WE DONT KNOW: Set auxiliary I/O 2 to inactive
        "SBM 2,0",  # WE DONT KNOW: Set auxiliary I/O 3 to inactive
        "SBM 3,0",  # WE DONT KNOW: Set lower limit temperature for Aux 1 to inactive
        "SBM 4,0",  # WE DONT KNOW: Set upper limit temperature for Aux 1 to inactive
        "SBM 5,0",  # WE DONT KNOW: Set lower limit temperature for Aux 2 to inactive
        "SBM 6,0",  # WE DONT KNOW: Set upper limit temperature for Aux 2 to inactive
        "SBM 7,0",  # WE DONT KNOW: Set lower limit temperature for Aux 3 to inactive
        "SBE 0",  # WE DONT KNOW: Disable buzzer
        "STS 1",  # Set temperature setpoint slope to 0.01°C/s
        "SAS 0",  # Disable cyclic sending of measurement values
        "SEI 0",  # Disable TEC-Controller control via external input
        "SFS 0",  # Set fan control sensor to inactive
        "SIM 0",  # Set interface mode to ASCII
        "SM1 0",  # Disable shutdown temperature for sensor 1
        "SM2 0",  # Disable shutdown temperature for sensor 2
        "SM3 6500",  # Set shutdown temperature for sensor 3 to 65.00°C
        "STI 0",  # Disable external temperature setpoint input
        "STD 0",  # Disable maximum temperature delta between sensor 1 and 2
        "SC0 0",  # WE DONT KNOW: Disable monitoring of sensor 1
        "SEN"  # Enable TEC-Controller
    ]
    
    for command in commands:
        formatted_command = f"{receiver_id} {command}"
        ascii_communication(port, formatted_command)
        
# Example usage:
port = "/dev/ttyUSB1"  # Change this based on your setup
command = "SDI\n"

response = ascii_communication_protocol(port, command)
print(f"Response from TEC controller: {response}")
