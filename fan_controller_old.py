import pigpio
import RPi.GPIO as GPIO
import time
from simple_pid import PID
from threading import Lock, Thread

GPIO.setmode(GPIO.BCM)

class FanController:
    def __init__(self, pwm_pin, pulse_rpm_pin, frequency = 25000, pulses_per_rev = 2):
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

        # ----- pigpio PWM on GPIO 12 -----
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("pigpiod is not running")

        # Start 25 kHz at 100 % duty via hardware PWM
        self.pi.hardware_PWM(self.pwm_pin, frequency, 500000)

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
        print(dt)
        current_count = self.rpm_count
        self.rpm_count = 0
        self.start_time = time.time()
        if dt > 0:
            self.pulse_rpm = (current_count / self.pulses_per_rev) / dt * 60.0
        else:
            self.pulse_rpm = 0

        print(self.pulse_rpm)

    def cleanup(self):
        """Cleanup PWM and GPIO."""
        GPIO.remove_event_detect(self.pulse_rpm_pin)
        self.pi.hardware_PWM(self.pwm_pin, self.frequency, 0)
        self.pi.stop()
        print("Cleaned up")


    

if __name__ == "__main__":
    # Example pins: adjust for your wiring
    tacho_pin_1 = 25   # Tachometer input pin
    pwm_pin_1 = 12     # Hardware PWM pin

    tacho_pin_2 = 16
    pwm_pin_2 = 13

    fan = FanController(pwm_pin=pwm_pin_1, pulse_rpm_pin=tacho_pin_1)
    fan2 = FanController(pwm_pin=pwm_pin_2, pulse_rpm_pin=tacho_pin_2)

    try:
        while True:
            time.sleep(10)
            fan.calculate_pulse_rpm()
            fan2.calculate_pulse_rpm()
    except KeyboardInterrupt:
        pass
    finally:
        fan.cleanup()
        fan2.cleanup()
        GPIO.cleanup()
