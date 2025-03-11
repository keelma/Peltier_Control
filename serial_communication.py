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

# Example usage:
port = "/dev/ttyUSB1"  # Change this based on your setup
command = "SDI\n"

response = ascii_communication_protocol(port, command)
print(f"Response from TEC controller: {response}")
