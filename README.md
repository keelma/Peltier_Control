## Overview
This project controls Peltier elements using a TEC (Thermoelectric Cooler) module. The system is managed by a Raspberry Pi, which regulates temperature by adjusting the TEC module's power.

## Features
- Temperature control using Peltier elements
- Raspberry Pi-based regulation
- TEC module to control current to Peltier elements

## Hardware
- Raspberry Pi
- Peltier elements
- TEC module

## Assign Fixed Port Names to TEC Modules on Raspberry Pi
To ensure that the TEC modules always have the same serial port names, follow these steps:

### 1. Create a udev rule
Run the following command:
```bash
sudo nano /etc/udev/rules.d/99-tec.rules
```
Then, add the following lines to specify the TEC modules based on their vendor and product IDs:
```bash
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="tec10"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="tec11"
```

### 2. Apply the New udev Rules
Reload and apply the rules with:
```bash
sudo udevadm control --reload-rules 
sudo udevadm trigger
```

### 3. Access the TEC Modules in Python
After setting up the rules, you can access the TEC modules in your Python script using the assigned names:
```python
import serial

# Open serial connections to the TEC modules
ser1 = serial.Serial('/dev/tec1', baudrate=9600, timeout=1) 
ser2 = serial.Serial('/dev/tec2', baudrate=9600, timeout=1)

print("TEC 1 connected:", ser1.name)
print("TEC 2 connected:", ser2.name)
```

## Contributors
- Max Keel
- Alex Zeller