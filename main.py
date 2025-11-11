import time
from datetime import datetime, timezone
import traceback
import threading
import statistics as pstdev
import numpy as np

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

# --------------- TEC MODULE CONFIG -----------------------

port = "/dev/ttyUSB0"
receiver_id = 10

tec_module = TECModule(port, receiver_id)

command_spannung = "GV1\n"
command_strom = "GCU\n"
command_10 = "SCU 0\n"

# ------------------ FAN CONFIG ---------------------------

import pigpio

pwm_pin_hs = 12
pwm_pin_cs = 13
pwm = pigpio.pi()
armed = False
start = True

# ------------------- FUNCTIONS ---------------------------

class Shared():

    def __init__(self):
        self._cond = threading.Condition()
        self._values = None
        self._version = 0
    
    def publish(self, values):
        with self._cond:
            self._values = values
            self._version += 1
            self._cond.notify_all()

    def wait_for_new(self, last_seen, timeout = None):
            with self._cond:
                if not self._cond.wait_for(lambda: self._version != last_seen, timeout = timeout):
                    return last_seen, None
                return self._version, self._values

shared = Shared()

def arm():
    global armed
    pwm.set_servo_pulsewidth(pwm_pin_cs, 2000)
    pwm.set_servo_pulsewidth(pwm_pin_hs, 2000)
    fan_pwm(2000)
    
    armed = True

    return armed

def disarm():
    global armed
    pwm.set_servo_pulsewidth(pwm_pin_cs, 2000)
    pwm.set_servo_pulsewidth(pwm_pin_hs, 2000)
    tec_module.ascii_communication_protocol(port,receiver_id, 0)

    armed = False

    return armed

def fan_pwm(pwm_value):
    pwm.set_servo_pulsewidth(pwm_pin_cs, pwm_value)
    pwm.set_servo_pulsewidth(pwm_pin_hs, pwm_value)


def check_for_stationary(values, std_tol = 0.2, span_tol = 0.2, min_n = 3):

    if values is None or values.shape[1] < min_n:
        print("BINGERBONGER")
        return False

    row_std = np.std(values, axis = 1)
    row_span = np.ptp(values, axis = 1)

    print ("I am Checking")
    if (row_std <= std_tol) or (row_span <= span_tol):
        print("Stationary")

    else:
        print("Not stationary")

    return ((row_std <= std_tol) or (row_span <= span_tol))

def tec_control():
    
    arm()

    if armed:
        last_seen = 0
        start_time = datetime.time()

        while not stationary:
            ver, vals = shared.wait_for_new(last_seen, timeout=20)
            if vals is None:
                continue
            
            last_seen = ver
            
            if check_for_stationary(values, std_tol = 0.2, span_tol = 0.2):
                stationary = True

        # Starting ramp test

        min_A = 0
        max_A = 50
        step_size = 10
        step_duration = 30 # in sec

        cooling_power = list(range(1000, 2001, 100))

        ramp_commands = [(tec_module.ascii_communication_protocol(port,receiver_id, f"SHC {max_A+1}\n")),
                (tec_module.ascii_communication_protocol(port,receiver_id, f"SCC {max_A+1}\n")),
                (tec_module.ascii_communication_protocol(port,receiver_id, command_strom)),
                (tec_module.ascii_communication_protocol(port,receiver_id, "GPW\n")),
                (tec_module.ascii_communication_protocol(port,receiver_id, command_spannung)),
                (tec_module.ascii_communication_protocol(port,receiver_id, command_strom))]

        for i in range (min_A, max_A+1, step_size):
            command_strom = f"SCU {i}\n"

            fan_pwm(2000)

            for func, args, kwargs in ramp_commands:
                _, flag = func(*args, *kwargs)

                if not flag:
                    break
            
            while not stationary:
                ver, vals = shared.wait_for_new(last_seen, timeout=20)
                if vals is None:
                    continue
                
                last_seen = ver
                
                if check_for_stationary(values, std_tol = 0.2, span_tol = 0.2):
                    stationary = True
            
            measurement_interval_sec = 5

            for elements in reversed(cooling_power):
                fan_pwm(elements)

                while not stationary:
                    ver, vals = shared.wait_for_new(last_seen, timeout=20)
                    if vals is None:
                        continue
                    
                    last_seen = ver
                    
                    if check_for_stationary(values, std_tol = 0.2, span_tol = 0.2):
                        stationary = True
                time.sleep(step_duration)

            measurement_interval_sec = 10

    disarm()
    start = False

def logging():
    global values
    while start:
        try:
            timestamp = datetime.now(timezone.utc)

            # --- RTD ---
            system_values = rtd_reader_system.read()
            control_values = rtd_reader_control.read()
            rtd_writer_system.write(timestamp, system_values)
            rtd_writer_control.write(timestamp, control_values)
            print(f"Temperature logged: {timestamp}")
            
            col = np.asarray(system_values, dtype=float)[:, None] 

            if values is None:
                values = col
            else:
                values = np.hstack([values, col])

            if values.shape[1] > 3:
                values = values[:, 1:]

            print (f"Values {values}")

            shared.publish(values)

            time.sleep(measurement_interval_sec)

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

    tec_control_thread.join()
    logging_thread.join()
    

    

# ----------------- START THREADS -------------------------

tec_control_thread = threading.Thread(target = tec_control)
logging_thread = threading.Thread(target = logging)

tec_control_thread.start()
logging_thread.start()

