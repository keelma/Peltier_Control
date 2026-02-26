import pigpio
import time
from simple_pid import PID
from threading import Lock, Thread

class Tachometer:
    """
    High-resolution tachometer measurement using pigpio timestamps.
    Measures time between rising edges and converts to RPM using:
        RPM = (1 / period) / pulses_per_rev * 60
    """
    def __init__(self, pi, pin, pulses_per_rev=2, glitch_us=100):
        """
        Parameters
        ----------
        pi : pigpio.pi()
            The pigpio instance.
        pin : int
            GPIO pin for tachometer input.
        pulses_per_rev : int
            Number of tach pulses per mechanical revolution.
        glitch_us : int
            Glitch filter duration in microseconds to remove noise.
        """
        self.pi = pi
        self.pin = pin
        self.pulses_per_rev = pulses_per_rev

        self.last_tick = None
        self.period = None  # seconds between pulses

        self.pi.set_mode(self.pin, pigpio.INPUT)
        self.pi.set_pull_up_down(self.pin, pigpio.PUD_UP)
        self.pi.set_glitch_filter(self.pin, glitch_us)

        self.cb = self.pi.callback(self.pin, pigpio.RISING_EDGE, self._callback)

    def _callback(self, gpio, level, tick):
        if self.last_tick is not None:
            dt_us = pigpio.tickDiff(self.last_tick, tick)  # microseconds
            if dt_us > 0:
                self.period = dt_us / 1e6  # convert to seconds
        self.last_tick = tick

    def read_rpm(self):
        if self.period is None:
            return 0.0
        return (1.0 / self.period) / self.pulses_per_rev * 60.0


class FanController:
    """
    Fan controller with hardware PWM and high-resolution tachometer feedback.
    Uses pigpio for both PWM and RPM measurement (no RPi.GPIO).
    """
    def __init__(self,
                 name,
                 pwm_pin,
                 pulse_rpm_pin,
                 target_rpm=8000,
                 frequency=25000,
                 pulses_per_rev=2,
                Kp=3,
                Kd=1,
                Ki=12,
                 update_interval=0.5):
        """
        Parameters
        ----------
        name : str
            Identifier for the fan.
        pwm_pin : int
            GPIO pin for hardware PWM.
        pulse_rpm_pin : int
            Tachometer pin.
        target_rpm : float
            Desired RPM setpoint.
        frequency : int
            PWM carrier frequency (25 kHz for PC fans).
        pulses_per_rev : int
            Tach pulses per revolution (almost always 2).
        Kp, Ki, Kd : float
            PID gains.
        update_interval : float
            Control loop interval in seconds.
        """
        self.name = name
        self.pwm_pin = pwm_pin
        self.target_rpm = target_rpm
        self.frequency = frequency
        self.update_interval = update_interval

        self.pulses_per_rev = pulses_per_rev

        self.lock = Lock()
        self.running = False

        # pigpio instance
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("pigpiod is not running")

        # Tachometer (high-resolution timestamp-based)
        self.tach = Tachometer(self.pi, pulse_rpm_pin, pulses_per_rev)

        # PID setup
        self.pid = PID(Kp=Kp, Ki=Ki, Kd=Kd, setpoint=target_rpm)
        self.pid.output_limits = (300000, 1000000)  # avoid windup
        self.pid.sample_time = update_interval

        # Initialize fan at mid duty
        self.pi.hardware_PWM(self.pwm_pin, self.frequency, 500000)

    def _set_pwm(self, value):
        self.pi.hardware_PWM(self.pwm_pin, self.frequency, int(value))

    def _control_loop(self):
        while self.running:
            rpm = self.tach.read_rpm()

            pwm = int(self.pid(rpm))
            self._set_pwm(pwm)

            #print(f"[Fan {self.name}] Target: {self.target_rpm} RPM | Measured: {rpm:.1f} | PWM: {pwm}")

            time.sleep(self.update_interval)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = Thread(target=self._control_loop, daemon=True)
            self.thread.start()

    def set_target_rpm(self, rpm):
        self.target_rpm = rpm
        self.pid.setpoint = rpm

    def get_target_rpm(self):
        return self.target_rpm

    def get_current_rpm(self):
        return self.tach.read_rpm()

    def cleanup(self):
        self.running = False
        time.sleep(self.update_interval * 2)
        self._set_pwm(0)
        self.pi.stop()
        print("Cleaned up fan controller.")
        

if __name__ == "__main__":
    pwm_pin = 12
    tach_pin = 25

    fan = FanController(
        name="HS_Fan",
        pwm_pin=pwm_pin,
        pulse_rpm_pin=tach_pin,
        target_rpm=15000,
        Kp=2, Ki=16, Kd=0.9,
        update_interval=0.5
    )
    fan.start()

    try:
        while True:
            time.sleep(30)
            fan.set_target_rpm(10000)
            #print(f"Current RPM: {fan.get_current_rpm():.0f}")
    except KeyboardInterrupt:
        pass
    finally:
        fan.cleanup()
