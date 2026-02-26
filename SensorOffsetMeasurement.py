import time
from datetime import datetime, timezone
import traceback
import threading
import numpy as np
import RPi.GPIO as GPIO

from fan_controller import FanController

from temperature_sensor_reader_rtd import TemperatureSensorReaderRTD
from temperature_sensor_writer_rtd import TemperatureSensorWriterRTD

from data_logger import SensorDataWriter

from TECModule import TECModule

import re

start = True
stop_requested = False   # NEW

print(f"Start Time: {datetime.now(timezone.utc)}")


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

measurement_interval_sec = 5
RETRY_WAIT_SECONDS = 10

# ------------------- RTD CONFIGURATION -------------------

NUMBER_OF_SENSORS = 8

boards_0_2 = {
    0: list(range(1, 9)),
    1: list(range(1, 9)),
    2: list(range(1, 9))
}
board_3 = {
    3: list(range(5, 9))
}

values = None

system_labels = [f"B{i}_CH{j}" for i in range(3) for j in range(1, 9)]  # 24 labels
control_labels = ["sensor_left_front","sensor_right_front","sensor_left_back","sensor_right_back"]

rtd_reader_system = TemperatureSensorReaderRTD(board_channel_map=boards_0_2)
rtd_reader_control = TemperatureSensorReaderRTD(board_channel_map=board_3)

rtd_writer_system = TemperatureSensorWriterRTD(
    influx_url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
    bucket=INFLUX_BUCKET,
    sensor_type="system_id",
    labels=system_labels,
)

rtd_writer_control = TemperatureSensorWriterRTD(
    influx_url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
    bucket=INFLUX_BUCKET,
    sensor_type="control",
    labels=control_labels,
)

sensor_data_writer = SensorDataWriter(
    influx_url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG,
    bucket=INFLUX_BUCKET,
    sensor_type="system_id",
    labels=system_labels,
)


# ------------------- FUNCTIONS ---------------------------

class Shared():

    def __init__(self):
        self._cond = threading.Condition()
        self._values = None
        self._version = 0
        self.current_i = 0.0
        self.min_n = 50

    def set_i(self, val):
        with self._cond:
            self.current_i = float(val)
            self._cond.notify_all()

    def get_i(self):
        with self._cond:
            return self.current_i

    def publish(self, values):
        with self._cond:
            self._values = values
            self._version += 1
            self._cond.notify_all()

    def wait_for_new(self, last_seen, timeout=None):
        with self._cond:
            if stop_requested:   # NEW
                return last_seen, None
            if not self._cond.wait_for(lambda: self._version != last_seen or stop_requested, timeout=timeout):
                return last_seen, None
            if stop_requested:
                return last_seen, None
            return self._version, self._values
            
    def get_min_n(self):
        return float(self.min_n)
    
shared = Shared()


def check_for_stationary(values, std_tol=0.1, span_tol=0.1):
    min_n = shared.get_min_n()

    if values is None or values.shape[1] < min_n:
        print("Not enough measurements")
        return False

    mask = np.all((values >= -40) & (values <= 200), axis=1)
    filtered = values[mask]

    row_std = np.std(filtered, axis=1)
    row_span = np.ptp(filtered, axis=1)

    print("I am Checking")
    if np.all((row_std <= std_tol) | (row_span <= span_tol)):
        print("Stationary")
        return True
    else:
        print("Not stationary")
        return False


def parse_tec_response(resp, label):
    if not isinstance(resp, tuple) or len(resp) < 2:
        print(f"Invalid TEC response structure for {label}: {resp}")
        return None

    text, ok = resp[0], resp[1]

    if not ok or text is None:
        print(f"TEC returned error for {label}: {resp}")
        return None

    match = re.search(r"=([\-0-9\.]+)", text)
    if not match:
        print(f"Could not parse TEC response for {label}: {text}")
        return None

    try:
        return float(match.group(1))
    except ValueError:
        print(f"Value parsing failed for {label}: {text}")
        return None


# ---------------- TEC CONTROL THREAD --------------------

def tec_control():
    global measurement_interval_sec
    global start

    start = True


# ---------------- LOGGING THREAD ------------------------

def logging():
    global values
    global start

    try:
        while start and not stop_requested:
            try:
                timestamp = datetime.now(timezone.utc)

                system_values = rtd_reader_system.read()

                rtd_writer_system.write(timestamp, system_values)

                print(f"Temperature logged: {timestamp}")

                col = np.asarray(system_values, dtype=float)[:, None]

                if values is None:
                    values = col
                else:
                    values = np.hstack([values, col])

                min_n = shared.get_min_n()
                if values.shape[1] > min_n:
                    values = values[:, 1:]

                mask = np.all((values >= -40) & (values <= 200), axis=1)
                filtered = values[mask]
                shared.publish(filtered)

                #print(filtered)

                for _ in range(measurement_interval_sec):
                    if stop_requested:
                        return
                    time.sleep(1)

            except Exception as e:
                break

    finally:
        pass


# ----------------- START THREADS -------------------------

try:
    start = True
    logging_thread = threading.Thread(target=logging)

    tec_control()
    logging_thread.start()
    logging_thread.join()

except KeyboardInterrupt:
    stop_requested = True
    with shared._cond:
        shared._cond.notify_all()

finally:
    rtd_writer_system.close()
    rtd_writer_control.close()
    time.sleep(1)
    GPIO.cleanup()
    print(f"End Time: {datetime.now(timezone.utc)}")
