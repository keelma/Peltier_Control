import pigpio
import RPi.GPIO as GPIO
import time
from simple_pid import PID
from threading import Lock, Thread

GPIO.setmode(GPIO.BCM)

class FanController:
    def __init__(self, name, pwm_pin, pulse_rpm_pin, target_rpm = 8000, frequency = 25000, pulses_per_rev = 2, Kp = 3, Ki = 19.2157, Kd = 0.0, update_interval=1.0): # 1 10 0.0
        """
        Initializes the FanController class with the specified GPIO pin.
        """
        self.pulse_rpm_pin = pulse_rpm_pin
        self.pwm_pin = pwm_pin
        self.rpm_count = 0
        self.start_time = time.time()
        self.pulse_rpm = 0
        self.frequency = frequency
        self.pulses_per_rev = pulses_per_rev

        self.name = name
        self.target_rpm = target_rpm
        self.Kp = Kp
        self.Kd = Kd
        self.Ki = Ki
        self.update_interval = update_interval

        self.lock = Lock()
        self.running = False

        self.pid = PID(Kp=self.Kp, Ki=self.Ki, Kd=self.Kd, setpoint=self.target_rpm)
        self.pid.output_limits = (300000, 1000000)

        # ----- pigpio PWM on GPIO 12 -----
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("pigpiod is not running")

        # Start 25 kHz at 100 % duty via hardware PWM
        self.pi.hardware_PWM(self.pwm_pin, self.frequency, 500000)

        # ----- RPi.GPIO for pulse counting -----
        GPIO.setup(self.pulse_rpm_pin, GPIO.IN)

        # Register RPi.GPIO interrupt (just like your original code)
        GPIO.add_event_detect(self.pulse_rpm_pin, GPIO.RISING, callback=self.count_pulses, bouncetime = 1)

    def count_pulses(self, channel):
        """Count pulses from ESC (RPi.GPIO callback)."""
        self.rpm_count += 1

    def calculate_pulse_rpm(self):
        """Calculate RPM based on counted pulses."""    

        dt = time.time() - self.start_time
        #print(dt)
        current_count = self.rpm_count
        self.rpm_count = 0
        self.start_time = time.time()
        if dt > 0:
            self.pulse_rpm = (current_count / self.pulses_per_rev) / dt * 60.0
        else:
            self.pulse_rpm = 0

        #print(self.pulse_rpm)
        return self.pulse_rpm

    def cleanup(self):
        """Cleanup PWM and GPIO."""
        GPIO.remove_event_detect(self.pulse_rpm_pin)
        self.pi.hardware_PWM(self.pwm_pin, self.frequency, 0)
        self.pi.stop()
        self.running = False
        if self.thread:
            self.thread.join()
        print("Cleaned up")

    def _set_pwm(self, value):
        self.pi.hardware_PWM(self.pwm_pin, self.frequency, value)

    def _control_loop(self):
        while self.running:
            with self.lock:
                current_rpm = self.calculate_pulse_rpm()
            pwm = self.pid(current_rpm)
            #print(pwm)
            self._set_pwm(int(pwm))
            print(f"[Fan {self.name}] Target: {self.target_rpm} RPM | Measured: {current_rpm:.1f} | PWM: {pwm:.2f}")
            time.sleep(self.update_interval)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = Thread(target=self._control_loop, daemon=True)
            self.thread.start()

    def set_target_rpm(self, rpm):
        self.target_rpm = rpm
        self.pid.setpoint = self.target_rpm

    def get_current_rpm(self):
        with self.lock:
            return self.pulse_rpm
        
    def set_update_interval(self, interval):
        self.update_interval = interval

    


if __name__ == "__main__":
    # Example pins: adjust for your wiring
    tacho_pin_1 = 25   # Tachometer input pin
    pwm_pin_1 = 19     # Hardware PWM pin

    tacho_pin_2 = 16 #16
    pwm_pin_2 = 13

    fan = FanController(name="HS_Fan", pwm_pin=pwm_pin_1, pulse_rpm_pin=tacho_pin_1, target_rpm = 15000, Kp = 0.9657, Ki = 9.2395, Kd = 0.3968)
    fan.start()

    #fan_2 = FanController(name="CS_FAN", pwm_pin = pwm_pin_2,pulse_rpm_pin=tacho_pin_2, target_rpm=15000, Kp = 3, Ki = 19.2157, Kd = 0.0)
    #fan_2.start()

    try:
        while True:
            time.sleep(30)
            fan.set_target_rpm(7000)
            #fan_2.set_target_rpm(7000)
            #print(f"Current RPM: {fan.get_current_rpm():.0f}")
    except KeyboardInterrupt:
        pass
    finally:
        fan.cleanup()
        #fan_2.cleanup()
        GPIO.cleanup()
