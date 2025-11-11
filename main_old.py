import time
from datetime import datetime, timezone
import traceback

from temperature_sensor_reader_rtd import TemperatureSensorReaderRTD
from temperature_sensor_writer_rtd import TemperatureSensorWriterRTD
from temperature_sensor_reader_tc import TemperatureSensorReaderTC
from temperature_sensor_writer_tc import TemperatureSensorWriterTC

from TECModule import TECModule

# ------------------- InfluxDB SETTINGS -------------------

INFLUX_URL = "http://82.130.67.100:8086"
INFLUX_TOKEN = "4MecLF8nQznwGWhGSPQhi6v_Y3dvyoHVqlUvF7JZqEDIZGWqvwdwQQBvZ-oEObwkpCjj4oHb8_uTFm8VmDSYvQ=="
INFLUX_ORG = "ThermoComp"
INFLUX_BUCKET = "Test_Max"

# ------------------- CSV PATHS (optional) ----------------

CSV_RTD_SYSTEM_PATH = "/home/raspberry/Desktop/TempDataLocal/rtd_system.csv"
CSV_RTD_CONTROL_PATH = "/home/raspberry/Desktop/TempDataLocal/rtd_control.csv"
CSV_TC_PATH = "/home/raspberry/Desktop/TempDataLocal/tc_data.csv"

# ------------------- MEASUREMENT INTERVAL ----------------

MEASUREMENT_INTERVAL_SEC = 10
RETRY_WAIT_SECONDS = 10

# ------------------- RTD CONFIGURATION -------------------

boards_0_2 = {
    0: list(range(1, 9)),
    1: list(range(1, 9)),
    2: list(range(1, 9))
}
board_3 = {
    3: list(range(5, 9))
}

system_labels = [f"B{i}_CH{j}" for i in range(3) for j in range(1, 9)]  # 24 labels
control_labels = ["sensor_left_front","sensor_right_front","sensor_left_back","sensor_right_back"]                 # 4 labels

rtd_reader_system = TemperatureSensorReaderRTD(board_channel_map=boards_0_2)
rtd_reader_control = TemperatureSensorReaderRTD(board_channel_map=board_3)

rtd_writer_system = TemperatureSensorWriterRTD(
    influx_url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
    bucket=INFLUX_BUCKET,
    sensor_type="system_id",
    labels=system_labels,
    # csv_file_path=CSV_RTD_SYSTEM_PATH
)

rtd_writer_control = TemperatureSensorWriterRTD(
    influx_url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
    bucket=INFLUX_BUCKET,
    sensor_type="control",
    labels=control_labels,
    # csv_file_path=CSV_RTD_CONTROL_PATH
)

# ------------------- TC CONFIGURATION --------------------


""" TC_LABEL_MAP = {
    "top front left": ("left_top", "temperature_front"),
    "top back left": ("left_top", "temperature_back"),
    "bottom front left": ("left_bottom", "temperature_front"),
    "bottom back left": ("left_bottom", "temperature_back"),
    "top front right": ("right_top", "temperature_front"),
    "top back right": ("right_top", "temperature_back"),
    "bottom front right": ("right_bottom", "temperature_front"),
    "bottom back right": ("right_bottom", "temperature_back"),
}

TC_BOARD_CHANNEL_MAP = {
    0: list(range(1, 9))
}

tc_reader = TemperatureSensorReaderTC(board_channel_map=TC_BOARD_CHANNEL_MAP)
tc_writer = TemperatureSensorWriterTC(
    influx_url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
    bucket=INFLUX_BUCKET,
    label_map=TC_LABEL_MAP,
    # csv_file_path=CSV_TC_PATH
) """

# --------------- TEC MODULE CONFIG -----------------------

port = "/dev/ttyUSB0"
receiver_id = 10

tec_module = TECModule(port, receiver_id)

command_spannung = "GV1\n"
command_strom = "GCU\n"
command_10 = "SCU 0\n"

# ------------------- MAIN LOOP ---------------------------

print("Starting full temperature logging (RTD + TC)...")

for i in range(50, 51, 10):
    command_10 = f"SCU {i}\n"

    tec_module.ascii_communication_protocol(port,receiver_id, "SHC 100\n")
    tec_module.ascii_communication_protocol(port,receiver_id, "SCC 100\n")
    tec_module.ascii_communication_protocol(port,receiver_id, command_10)
    time.sleep(1)
    tec_module.ascii_communication_protocol(port,receiver_id, "GPW\n")
    tec_module.ascii_communication_protocol(port,receiver_id, command_spannung)
    time.sleep(1)
    tec_module.ascii_communication_protocol(port,receiver_id, command_strom)

    time_now = datetime.now()

    while ((datetime.now()-time_now).total_seconds() < 600):
        try:
            timestamp = datetime.now(timezone.utc)

            # --- RTD ---
            system_values = rtd_reader_system.read()
            control_values = rtd_reader_control.read()
            rtd_writer_system.write(timestamp, system_values)
            rtd_writer_control.write(timestamp, control_values)
            print(f"System values: {system_values}")
            print(f"Control values: {control_values}")
            print(f"Temperature logged: {timestamp}")

            """ # --- TC ---
            tc_values = tc_reader.read()
            tc_writer.write(timestamp, tc_values)
            print("Temperature written.")
            time.sleep(MEASUREMENT_INTERVAL_SEC) """

            time.sleep(MEASUREMENT_INTERVAL_SEC)

        except KeyboardInterrupt:
            print("Logging stopped by user.")
            break
        except Exception as e:
            print("Error occured:")
            traceback.print_exc()
            print(f"Restarting in {RETRY_WAIT_SECONDS} seconds...\n")
            time.sleep(RETRY_WAIT_SECONDS)

        finally:
            rtd_writer_system.close()
            rtd_writer_control.close()
            """ tc_writer.close() """

    tec_module.ascii_communication_protocol(port,receiver_id, "SCU 0\n")
