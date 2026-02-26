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

#Logging the measurement protocol

import os
import csv
file_path = "measurement_protocol.csv"

file_exists = os.path.isfile(file_path)

if not file_exists:
    with open(file_path, mode="w", newline="", encoding = "utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["start_time", "end_time", "set_urrent", "set_rpm", "start_time_stat", "end_time_stat"])

start = True
stop_requested = False   # NEW



print(f"Start Time: {datetime.now(timezone.utc)}")
start_time = datetime.now(timezone.utc)

with open(file_path, mode="a", newline="", encoding = "utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([start_time, None, None, None, None, None])

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

measurement_interval_sec = 10
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


# ------------------ FAN CONFIG ---------------------------

tacho_hs = 25
pwm_hs = 12

tacho_cs = 16
pwm_cs = 13

fan_hs = FanController(name="fan_hs", pwm_pin=pwm_hs, pulse_rpm_pin=tacho_hs, target_rpm=15000, Kp=2, Kd=0.0, Ki=14)
fan_cs = FanController(name="fan_cs", pwm_pin=pwm_cs, pulse_rpm_pin=tacho_cs, target_rpm=15000, Kp=2.5, Ki=14, Kd=0.0)
fan_hs.start()
fan_cs.start()


# --------------- TEC MODULE CONFIG -----------------------

port = "/dev/ttyUSB0"
receiver_id = 10

tec_module = TECModule(port, receiver_id)
command_spannung = "GV1\n"
command_strom = "GCU\n"
command_10 = "SCU 0\n"


# ------------------- FUNCTIONS ---------------------------

class Shared():

    def __init__(self):
        self._cond = threading.Condition()
        self._values = None
        self._version = 0
        self.current_i = 0.0
        self.min_n = 120

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

    last_seen = 0
    stationary = False

    while not stationary and not stop_requested:
        ver, vals = shared.wait_for_new(last_seen, timeout=20)
        if stop_requested:
            return
        if vals is None:
            continue
        last_seen = ver

        if check_for_stationary(vals):
            stationary = True

    if stop_requested:
        return

    # Starting ramp test

    min_A = 100
    max_A = 202
    step_size = 100
    step_duration = 600

    cooling_power = list(range(15000, 9999, -5000))

    fan_hs.set_target_rpm(15000)
    fan_cs.set_target_rpm(15000)

    if max_A < 0:
        print("COOLING")
        i = max_A*(-1)
        tec_module.ascii_communication_protocol(port, receiver_id, f"SHC {i-1}\n")
        time.sleep(1)
        tec_module.ascii_communication_protocol(port, receiver_id, f"SCC {i-1}\n")
        time.sleep(1)

    else:
        print("HEATING")
        tec_module.ascii_communication_protocol(port, receiver_id, f"SHC {max_A+1}\n")
        time.sleep(1)
        tec_module.ascii_communication_protocol(port, receiver_id, f"SCC {max_A+1}\n")
        time.sleep(1)


    ramp_commands = [command_spannung, command_strom, "GPW\n"]

    for i in range(min_A, max_A+1, step_size):
        print("--------------------stop requested ?------------------------")
        if stop_requested:
            return
        print("--------------------stop not requested------------------------")

        shared.set_i(i)        
    
        print(f"----------Heating Current: {i/100} A----------")
        command_strom_set = f"SCU {i}\n"

        for cmd in ramp_commands:
            resp = tec_module.ascii_communication_protocol(port, receiver_id, cmd)
            if isinstance(resp, tuple) and len(resp) >= 2 and not resp[1]:
                break

        tec_module.ascii_communication_protocol(port, receiver_id, command_strom_set)

        stationary = False
        # while not stationary and not stop_requested:
        #     ver, vals = shared.wait_for_new(last_seen, timeout=20)
        #     if stop_requested:
        #         return
        #     if vals is None:
        #         continue
        #     last_seen = ver
        #     if check_for_stationary(vals):
        #         stationary = True
        
        # if stop_requested:
        #     return

        measurement_interval_sec = 5

        for rpm in cooling_power:
            if stop_requested:
                return

            # stationary = False
            # while not stationary and not stop_requested:
            #     ver, vals = shared.wait_for_new(last_seen, timeout=20)
            #     if stop_requested:
            #         return
            #     if vals is None:
            #         continue
            #     last_seen = ver
            #     if check_for_stationary(vals):
            #         stationary = True
            #         print("Stationary")

            #fan_hs.set_target_rpm(rpm)
            fan_cs.set_target_rpm(rpm)
            print(f"Target rpm: {rpm}")
            time.sleep(800)
            stationary = False
            while not stationary and not stop_requested:
                ver, vals = shared.wait_for_new(last_seen, timeout=20)
                if stop_requested:
                    return
                if vals is None:
                    continue
                last_seen = ver
                if check_for_stationary(vals):
                    stationary = True

            if stop_requested:
                return
            
            start_time_stat = datetime.now(timezone.utc)
            time.sleep(step_duration)
            end_time_stat = datetime.now(timezone.utc)

            with open(file_path, mode="a", newline="", encoding = "utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([None, None, shared.get_i()/100, rpm, start_time_stat, end_time_stat])

        measurement_interval_sec = 10

    start = False


# ---------------- LOGGING THREAD ------------------------

def logging():
    global values
    global start

    try:
        while start and not stop_requested:
            try:
                current = parse_tec_response(
                    tec_module.ascii_communication_protocol(port, receiver_id, "GCU\n"),
                    "current"
                )

                voltage_plus = parse_tec_response(
                    tec_module.ascii_communication_protocol(port, receiver_id, "GV1\n"),
                    "voltage_plus"
                )

                voltage_minus = parse_tec_response(
                    tec_module.ascii_communication_protocol(port, receiver_id, "GV2\n"),
                    "voltage_minus"
                )

                if current is None or voltage_plus is None or voltage_minus is None:
                    print("Invalid TEC response detected. Skipping this logging cycle.")
                    time.sleep(RETRY_WAIT_SECONDS)
                    continue

                rpm_fan_hs = fan_hs.get_current_rpm()
                rpm_fan_cs = fan_cs.get_current_rpm()

                set_current = shared.get_i() / 100

                set_rpm_hs = fan_hs.get_target_rpm()
                set_rpm_cs = fan_cs.get_target_rpm()

                print(f"Current: {current}, V+: {voltage_plus}, V-: {voltage_minus}, "
                      f"RPM HS: {rpm_fan_hs}, RPM CS: {rpm_fan_cs}")

                timestamp = datetime.now(timezone.utc)

                system_values = rtd_reader_system.read()

                rtd_writer_system.write(timestamp, system_values)

                sensor_data_writer.write_tec(timestamp, "tec_module_kühner",
                                             set_current, current, voltage_plus, voltage_minus)
                sensor_data_writer.write_rpm(timestamp, "fan_hs", set_rpm_hs, rpm_fan_hs)
                sensor_data_writer.write_rpm(timestamp, "fan_cs", set_rpm_cs, rpm_fan_cs)

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
    tec_control_thread = threading.Thread(target=tec_control)
    logging_thread = threading.Thread(target=logging)

    tec_control_thread.start()
    logging_thread.start()

    tec_control_thread.join()
    logging_thread.join()

except KeyboardInterrupt:
    stop_requested = True
    with shared._cond:
        shared._cond.notify_all()

finally:
    tec_module.ascii_communication_protocol(port, receiver_id, "SCU 0\n")
    rtd_writer_system.close()
    rtd_writer_control.close()
    print(f"End Time: {datetime.now(timezone.utc)}")
    end_time = datetime.now(timezone.utc)
    with open(file_path, mode="a", newline="", encoding = "utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([None, end_time, None, None, None, None])
    fan_hs.cleanup()
    fan_cs.cleanup()
    time.sleep(1)
    GPIO.cleanup()
    
