import serial
import time

def ascii_communication_protocol(port: str, receiver_id: str, command: str):
    ser = serial.Serial(port, baudrate = 9600, timeout=1)

    # Flush input to clear any existing data
    ser.reset_input_buffer()
    formatted_command = f"{receiver_id} {command}"
    print(f"Sending command: {formatted_command.strip()} to {port}")

    ser.write(formatted_command.encode('ascii'))

    time.sleep(1)

    response = ser.read(ser.in_waiting).decode('ascii').strip()

    ser.close()
    print(f"Response from TEC controller: {response}")
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
        "SDI\n",  # Disable TEC-Controller
        "SPF 000\n",  # Set proportional factor to 0
        "SIF 000\n",  # Set integral factor to 0
        "SDF 000\n",  # Set differential factor to 0
        "SHC 1600\n",  # Set heating current limit to 10.00 A
        "SCC 0\n",  # Set cooling current limit to 10.00 A
        "SMA 6000\n",  # Set maximum temperature to 60.00°C
        "SMI 0\n",  # Set minimum temperature to 0.00°C
        "SAE 0\n",  # Disable automatic enabling
        "SUS 1\n",  # Use temperature sensor 1 for regulation
        "SBM 0,0\n",  # WE DONT KNOW: Set auxiliary I/O 1 to inactive
        "SBM 1,0\n",  # WE DONT KNOW: Set auxiliary I/O 2 to inactive
        "SBM 2,0\n",  # WE DONT KNOW: Set auxiliary I/O 3 to inactive
        "SBM 3,0\n",  # WE DONT KNOW: Set lower limit temperature for Aux 1 to inactive
        "SBM 4,0\n",  # WE DONT KNOW: Set upper limit temperature for Aux 1 to inactive
        "SBM 5,0\n",  # WE DONT KNOW: Set lower limit temperature for Aux 2 to inactive
        "SBM 6,0\n",  # WE DONT KNOW: Set upper limit temperature for Aux 2 to inactive
        "SBM 7,0\n",  # WE DONT KNOW: Set lower limit temperature for Aux 3 to inactive
        "SBE 0\n",  # WE DONT KNOW: Disable buzzer
        "STS 1\n",  # Set temperature setpoint slope to 0.01°C/s
        "SAS 0\n",  # Disable cyclic sending of measurement values
        "SEI 0\n",  # Disable TEC-Controller control via external input
        "SFS 0\n",  # Set fan control sensor to inactive
        "SIM 0\n",  # Set interface mode to ASCII
        "SM1 0\n",  # Disable shutdown temperature for sensor 1
        "SM2 0\n",  # Disable shutdown temperature for sensor 2
        "SM3 6500\n",  # Set shutdown temperature for sensor 3 to 65.00°C
        "STI 0\n",  # Disable external temperature setpoint input
        "STD 0\n",  # Disable maximum temperature delta between sensor 1 and 2
        "SC0 0\n",  # WE DONT KNOW: Disable monitoring of sensor 1
        "SEN\n"  # Enable TEC-Controller
    ]
    
    for command in commands:
        ascii_communication_protocol(port,receiver_id,command)
        
# Example usage:
port = "/dev/ttyUSB0"  # Change this based on your setup
command_spannung = "GV1\n"
command_strom = "GCU\n"
command = "SCU 100\n"
#command = "SCU 0\n"
receiver_id_11 = "11"
receiver_id_10 = "10"
#tec_initalisation(receiver_id_10,port)
response = ascii_communication_protocol(port,receiver_id_10, command)
time.sleep(1)
ascii_communication_protocol(port,receiver_id_10, command_spannung)
time.sleep(1)
ascii_communication_protocol(port,receiver_id_10, command_strom)
time.sleep(10)
ascii_communication_protocol(port,receiver_id_10, "SCU 0\n")
