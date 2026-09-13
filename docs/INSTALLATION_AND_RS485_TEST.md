# Installation, CraftBeerPi service and RS485 test

This document records the setup and test procedure used for the first working installation of `cbpi4-sdm630`.

## Tested CraftBeerPi installation

The Raspberry Pi runs CraftBeerPi 4 via `pipx`.

Verified with:

```bash
pipx list
```

Result during setup:

```text
package cbpi4 4.7.4, installed using Python 3.13.5
- cbpi
```

The pipx virtual environment is located below the user home directory, e.g.:

```text
/home/wallbox/.local/share/pipx/venvs/cbpi4
```

Plugins therefore have to be installed into the `cbpi4` pipx environment.

Example installation directly from GitHub:

```bash
pipx runpip cbpi4 install https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
```

A successful installation ends with output similar to:

```text
Successfully installed cbpi4-sdm630-0.1.0 minimalmodbus-2.1.1
```

## Update an existing plugin installation

To update the plugin to the newest version from the GitHub `main` branch:

```bash
pipx runpip cbpi4 install --upgrade https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
```

Then restart CraftBeerPi so the new plugin code is loaded:

```bash
sudo systemctl restart craftbeerpi.service
```

Check the installed package version with:

```bash
pipx runpip cbpi4 show cbpi4-sdm630
```

The loaded plugin version can also be checked in the CraftBeerPi web interface on the Plugins page.

If the GitHub repository contains changed code but the package version in `setup.py` has not changed, pip may decide that nothing needs to be updated. In that case force a reinstall:

```bash
pipx runpip cbpi4 install --upgrade --force-reinstall https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
sudo systemctl restart craftbeerpi.service
```

This does not delete the existing CraftBeerPi hardware/sensor configuration; it replaces the installed Python package in the `cbpi4` pipx environment.

## CraftBeerPi service / restart

Current CraftBeerPi installations use the CraftBeerPi autostart mechanism (`cbpi autostart on`) and a systemd unit named `craftbeerpi.service`.

Useful commands:

```bash
systemctl status craftbeerpi.service
sudo systemctl restart craftbeerpi.service
```

If the service is installed as a user service instead, use:

```bash
systemctl --user status craftbeerpi.service
systemctl --user restart craftbeerpi.service
```

To find the actual active service on a particular installation:

```bash
systemctl list-units --type=service | grep -i craftbeer
systemctl --user list-units --type=service | grep -i craftbeer
```

The official CraftBeerPi command for starting the server manually is:

```bash
cbpi start
```

## RS485 hardware used for the test

USB/RS485 adapter:

```text
FTDI USB-RS485-WE / FT232R
```

Linux detected the adapter as:

```text
/dev/ttyUSB0
```

The stable by-id path was:

```text
/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0
```

This path is preferred over `/dev/ttyUSB0`, because `/dev/ttyUSB0` can change after reconnecting USB devices.

### Check the adapter

```bash
ls -l /dev/ttyUSB*
```

Working result:

```text
crw-rw----+ 1 root plugdev 188, 0 ... /dev/ttyUSB0
```

Then check the persistent device name:

```bash
ls -l /dev/serial/by-id/
```

Working result:

```text
usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0 -> ../../ttyUSB0
```

### User permissions

Check group membership:

```bash
groups
```

The user used during the test was already a member of the serial related groups, including `dialout` and `plugdev`.

## FTDI USB-RS485-WE wire assignment

For the FTDI USB-RS485-WE cable used during the test:

| Wire | Function |
|---|---|
| Black | GND |
| Brown | Terminator 1 |
| Red | +5 V output |
| Orange | Data+ / A |
| Yellow | Data- / B |
| Green | Terminator 2 |

The brown and green wires are the two ends of the internal 120 ohm termination resistor. Only connect them across A/B when the USB/RS485 adapter is physically located at an end of the RS485 bus and termination is required.

Do not use the red +5 V wire to power the SDM630.

## SDM630 Modbus settings used during the test

```text
Protocol: Modbus RTU
Slave address: 1
Baudrate: 9600
Data bits: 8
Parity: none
Stop bits: 1
Format: 8N1
Function code: 04 (Read Input Registers)
Float format: IEEE754 FLOAT32, big endian
```

## Step-by-step RS485 communication test

The SDM630 was deliberately tested outside CraftBeerPi first. This separates serial/Modbus problems from plugin problems.

### 1. Create a Python virtual environment

```bash
python3 -m venv ~/sdmtest
```

### 2. Activate it

```bash
source ~/sdmtest/bin/activate
```

The shell prompt should then start with something similar to:

```text
(sdmtest)
```

### 3. Install the Modbus test packages

```bash
python -m pip install minimalmodbus pyserial
```

Do not install the test packages globally with `pip --user` on current Raspberry Pi OS, because PEP 668 marks the system Python environment as externally managed.

### 4. Test script

Create `~/sdmtest_sdm630.py` with the following content:

```python
import minimalmodbus
import serial

PORT = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0"
SLAVE = 1

meter = minimalmodbus.Instrument(PORT, SLAVE, mode=minimalmodbus.MODE_RTU)
meter.serial.baudrate = 9600
meter.serial.bytesize = 8
meter.serial.parity = serial.PARITY_NONE
meter.serial.stopbits = 1
meter.serial.timeout = 0.5
meter.clear_buffers_before_each_transaction = True

registers = {
    "L1": 12,
    "L2": 14,
    "L3": 16,
    "Gesamt": 52,
}

for name, address in registers.items():
    value = meter.read_float(
        registeraddress=address,
        functioncode=4,
        number_of_registers=2,
        byteorder=minimalmodbus.BYTEORDER_BIG,
    )
    print(f"{name}: {value:.1f} W")
```

### 5. Run the test

```bash
python ~/sdmtest_sdm630.py
```

The first successful test returned:

```text
L1: 36.4 W
L2: 22.5 W
L3: 55.0 W
Gesamt: 82.7 W
```

This confirmed that all of the following were working before the CraftBeerPi plugin was installed:

- USB adapter detection
- Linux serial permissions
- RS485 A/B wiring
- SDM630 slave address
- baudrate and framing
- Modbus RTU communication
- SDM630 power-register decoding

### 6. Leave the test environment

```bash
deactivate
```

## SDM630 registers used by the plugin

| Measurement | SDM register notation | Modbus PDU address | Data type |
|---|---:|---:|---|
| L1 active power | 30013 | 12 | FLOAT32 |
| L2 active power | 30015 | 14 | FLOAT32 |
| L3 active power | 30017 | 16 | FLOAT32 |
| Total system active power | 30053 | 52 | FLOAT32 |

The plugin uses Modbus function code `04` for these input registers.

## Troubleshooting order

If CraftBeerPi does not show SDM630 values, verify the system in this order:

1. `ls -l /dev/serial/by-id/`
2. check the FTDI adapter is still present
3. check RS485 A/B polarity
4. check SDM630 slave address = 1
5. check 9600 baud, 8N1
6. run the standalone Python test again
7. only after the standalone test succeeds, troubleshoot the CraftBeerPi plugin

This procedure avoids mixing serial-bus problems with CraftBeerPi configuration problems.
