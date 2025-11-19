import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from bayes_opt import BayesianOptimization
import RPi.GPIO as GPIO

from fan_controller import FanController


class LivePlot:
    """
    Real-time plot for both fans during tuning.
    Call update(rpm1, rpm2) at each sampling step.
    """

    def __init__(self, target):
        self.target = target
        self.t = []
        self.rpm1 = []
        self.rpm2 = []

        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(10, 5))
        self.line1, = self.ax.plot([], [], label="Fan1 RPM")
        self.line2, = self.ax.plot([], [], label="Fan2 RPM")
        self.ax.axhline(self.target, linestyle='--', color='gray', label="Target")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("RPM")
        self.ax.legend()
        self.ax.grid(True)

        self.start_time = time.time()

    def update(self, r1, r2):
        dt = time.time() - self.start_time
        self.t.append(dt)
        self.rpm1.append(r1)
        self.rpm2.append(r2)

        self.line1.set_data(self.t, self.rpm1)
        self.line2.set_data(self.t, self.rpm2)
        self.ax.set_xlim(0, max(5, dt))
        self.ax.set_ylim(0, max(20000, r1, r2) * 1.1)
        plt.pause(0.001)


class FanPIDTuner:
    """
    Tunes ONE fan using Bayesian optimization.
    Will be instantiated twice for independent tuning.
    """

    def __init__(self, fan: FanController,
                 settle_time=8.0,
                 sample_interval=0.5,
                 target_rpm=15000):

        self.fan = fan
        self.settle_time = settle_time
        self.sample_interval = sample_interval
        self.target_rpm = target_rpm

    def run_step(self):
        """
        Runs a 0 → target step response, returns time and rpm arrays.
        """
        self.fan.set_target_rpm(self.target_rpm)

        samples = int(self.settle_time / self.sample_interval)
        t = np.linspace(0, self.settle_time, samples)
        rpm = []

        #live = LivePlot(self.target_rpm)

        for _ in range(samples):
            r = self.fan.get_current_rpm()
            rpm.append(r)
            #live.update(r, 0)
            time.sleep(self.sample_interval)
        

        return t, np.array(rpm)

    @staticmethod
    def rise_time(t, y, target):
        """
        Time between 10% and 90% of target.
        """
        y10 = 0.1 * target
        y90 = 0.9 * target

        try:
            t10 = t[np.where(y >= y10)[0][0]]
            t90 = t[np.where(y >= y90)[0][0]]
            return t90 - t10
        except:
            return t[-1]

    @staticmethod
    def mid_slope(t, y, target):
        """
        Slope at 50% rise point.
        """
        y50 = 0.5 * target
        idx = np.where(y >= y50)[0]
        if len(idx) < 2:
            return 0
        i = idx[0]
        if i == 0:
            return 0
        return (y[i] - y[i - 1]) / (t[i] - t[i - 1])

    @staticmethod
    def undershoot(y, target):
        return max(0, target - min(y))

    def evaluate_pid(self, Kp, Ki, Kd):
        """
        Bayesian optimizer calls this. Returns performance score.
        LOWER score = better.
        """

        # Apply PID
        self.fan.pid.tunings = (Kp, Ki, Kd)

        # Run step response
        t, y = self.run_step()

        # Compute metrics
        error = np.abs(self.target_rpm - y)
        iae = np.sum(error) * self.sample_interval

        overshoot = max(0, np.max(y) - self.target_rpm)
        rise = self.rise_time(t, y, self.target_rpm)
        mid = self.mid_slope(t, y, self.target_rpm)
        under = self.undershoot(y, self.target_rpm)

        # Multi-term objective
        score = (
            iae * 1.0 +
            overshoot * 0.3 -
            mid * 0.1 +       # faster slope is good
            rise * 0.1 +
            under * 0.2
        )

        return -score  # Bayesian Optimizer maximizes → invert

    def tune(self):
        """
        Bayesian optimization over PID params.
        Search ranges adapted for your hardware.
        """

        optimizer = BayesianOptimization(
            f=self.evaluate_pid,
            pbounds={
                "Kp": (0.5, 3.0),
                "Ki": (1, 25),
                "Kd": (0.0, 1.0)
            },
            verbose=2,
            random_state=1
        )

        optimizer.maximize(
            init_points=5,
            n_iter=20
        )

        best = optimizer.max["params"]
        print("\nBEST PID:", best)

        # Apply best values
        self.fan.pid.tunings = (
            best["Kp"],
            best["Ki"],
            best["Kd"],
        )

        return best


if __name__ == "__main__":
    GPIO.setmode(GPIO.BCM)

    fan1 = FanController("HS_Fan", pwm_pin=12, pulse_rpm_pin=25, target_rpm=15000)
    fan2 = FanController("CS_FAN", pwm_pin=13, pulse_rpm_pin=16, target_rpm=15000)

    fan1.start()
    fan2.start()

    tuner1 = FanPIDTuner(fan1)
    tuner2 = FanPIDTuner(fan2)

    print("Tuning FAN 1...")
    best1 = tuner1.tune()

    print("Tuning FAN 2...")
    best2 = tuner2.tune()

    print("Final PID values:")
    print("Fan 1:", best1)
    print("Fan 2:", best2)

    fan1.cleanup()
    fan2.cleanup()
    GPIO.cleanup()
