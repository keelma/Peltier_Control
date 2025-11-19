import lgpio
import time

# GPIO pin
PULSE_PIN = 24        # BCM pin for tach input
PULSES_PER_REV = 2    # your tacho gives 2 pulses per revolution

# global counters
pulse_count = 0       
rpm = 0.0
last_time = time.time()

# open gpiochip0
chip = lgpio.gpiochip_open(0)

# claim the GPIO as an alert source (edge detector)
# You MUST do this before registering the callback
lgpio.gpio_claim_alert(chip, PULSE_PIN, lgpio.FALLING_EDGE)

# pulse callback function
def pulse_callback(chip, gpio, level, timestamp):
    global pulse_count
    pulse_count += 1

# register callback
cb = lgpio.callback(chip, PULSE_PIN, lgpio.FALLING_EDGE, pulse_callback)

def calculate_rpm():
    global pulse_count, last_time, rpm

    now = time.time()
    dt = now - last_time
    if dt <= 0:
        return rpm

    count = pulse_count
    print(pulse_count)
    pulse_count = 0
    last_time = now

    rpm = (count / PULSES_PER_REV) * (60.0 / dt)
    return rpm

try:
    while True:
        value = calculate_rpm()
        print(f"RPM: {value:.1f}")
        time.sleep(0.2)

except KeyboardInterrupt:
    pass

finally:
    cb.cancel()
    lgpio.gpiochip_close(chip)
    print("Stopped.")
