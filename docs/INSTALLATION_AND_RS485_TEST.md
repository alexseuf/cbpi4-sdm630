# Installation, CraftBeerPi configuration and RS485 test

This document records the setup and test procedure used for the working `cbpi4-sdm630` installation.

## Tested CraftBeerPi installation

The Raspberry Pi runs CraftBeerPi 4 via `pipx`.

```bash
pipx list
```

Tested setup:

```text
package cbpi4 4.7.4, installed using Python 3.13.5
- cbpi
```

The pipx virtual environment is located below the user home directory, e.g.:

```text
/home/wallbox/.local/share/pipx/venvs/cbpi4
```

Install the plugin into this environment:

```bash
pipx runpip cbpi4 install https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
sudo systemctl restart craftbeerpi.service
```

## Update an existing plugin installation

```bash
pipx runpip cbpi4 install --upgrade https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
sudo systemctl restart craftbeerpi.service
```

Check the installed version:

```bash
pipx runpip cbpi4 show cbpi4-sdm630
```

If necessary, force a reinstall:

```bash
pipx runpip cbpi4 install --upgrade --force-reinstall https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
sudo systemctl restart craftbeerpi.service
```

This replaces the Python package but does not delete the existing CraftBeerPi hardware/sensor configuration.

## CraftBeerPi hardware configuration

In **Hardware → Sensors**, add a new sensor and select:

```text
Type: SDM630 Power
```

The `Messwert` menu provides the phase powers, total power, phase voltages, phase currents, cumulative energy and the resettable short-term energy counters.

![SDM630 measurement selection in CraftBeerPi](images/hardware-options.jpg)

### Recommended communication settings

```text
Port:      select the correct /dev/serial/by-id/... device
Slave:     1
Baudrate:  9600
Parity:    N
Stopbits:  1
Intervall: 2 s
Timeout:   0.5 s
```

If fields are left empty, the plugin applies internal defaults. If multiple serial adapters are connected, explicitly select the correct stable `/dev/serial/by-id/...` path.

Create a separate CraftBeerPi sensor instance for every measurement you want to display. All instances for the same physical SDM630 should use identical serial settings.

### Resettable short-term energy counters – v0.1.5

Two derived measurements are available:

```text
Kurzzeitzähler Bezug
Kurzzeitzähler Einspeisung
```

They behave like a trip counter. The action `Kurzzeitzähler nullen` resets both counters together while leaving the SDM630's cumulative import/export registers unchanged.

The baseline is persisted in:

```text
~/.craftbeerpi4-sdm630/short_term_counters.json
```

Therefore the counters survive CraftBeerPi restarts and Raspberry Pi reboots.

A configured dashboard can look like this:

![CraftBeerPi dashboard with SDM630](images/dashboard.jpg)

For the energy widgets, use `kWh` as the displayed unit. Three decimal places give a resolution of 0.001 kWh = 1 Wh.

## CraftBeerPi service / restart

Useful commands:

```bash
systemctl status craftbeerpi.service
sudo systemctl restart craftbeerpi.service
```

If the service is installed as a user service instead:

```bash
systemctl --user status craftbeerpi.service
systemctl --user restart craftbeerpi.service
```

To locate the active service:

```bash
systemctl list-units --type=service | grep -i craftbeer
systemctl --user list-units --type=service | grep -i craftbeer
```

## RS485 hardware used for the test

USB/RS485 adapter:

```text
FTDI USB-RS485-WE / FT232R
```

Linux detected the adapter as `/dev/ttyUSB0`. The stable by-id path used during testing was:

```text
/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0
```

Prefer the by-id path because `/dev/ttyUSB0` can change when USB devices are reconnected.

### Check the adapter

```bash
ls -l /dev/ttyUSB*
ls -l /dev/serial/by-id/
```

### User permissions

```bash
groups
```

The tested user was already a member of the serial-related groups including `dialout` and `plugdev`.

## FTDI USB-RS485-WE wire assignment

| Wire | Function | Connect to meter |
|---|---|---|
| Black | GND | GND, if used |
| Brown | Terminator 1 | termination only |
| Red | +5 V output | **do not connect to SDM630 power** |
| Orange | Data+ / A | RS485 A |
| Yellow | Data- / B | RS485 B |
| Green | Terminator 2 | termination only |

The brown and green wires are the two ends of the cable's internal 120-ohm termination resistor. Use the termination only when the adapter is physically at an end of the RS485 bus and termination is required.

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

Testing the SDM630 outside CraftBeerPi first separates serial/Modbus problems from plugin problems.

### 1. Create and activate a Python virtual environment

```bash
python3 -m venv ~/sdmtest
source ~/sdmtest/bin/activate
python -m pip install minimalmodbus pyserial
```

### 2. Test script

Create `~/sdmtest_sdm630.py`:

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

Run it:

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

This confirms USB detection, Linux permissions, A/B wiring, slave address, serial framing, Modbus RTU communication and FLOAT32 decoding independently of CraftBeerPi.

Leave the test environment with:

```bash
deactivate
```

## Registers used by the plugin

| Measurement | SDM register | PDU address | Unit |
|---|---:|---:|---|
| Voltage L1 | 30001 | 0 | V |
| Voltage L2 | 30003 | 2 | V |
| Voltage L3 | 30005 | 4 | V |
| Current L1 | 30007 | 6 | A |
| Current L2 | 30009 | 8 | A |
| Current L3 | 30011 | 10 | A |
| Active power L1 | 30013 | 12 | W |
| Active power L2 | 30015 | 14 | W |
| Active power L3 | 30017 | 16 | W |
| Total active power | 30053 | 52 | W |
| Total import energy | 30073 | 72 | kWh |
| Total export energy | 30075 | 74 | kWh |

All direct values are read with Modbus function code `04` as IEEE-754 FLOAT32 values. The two short-term counters are calculated by the plugin and therefore have no native SDM630 register address.

## Troubleshooting order

If CraftBeerPi does not show SDM630 values, verify in this order:

1. `ls -l /dev/serial/by-id/`
2. FTDI adapter present
3. correct serial adapter selected in CraftBeerPi
4. RS485 A/B polarity
5. SDM630 slave address = 1
6. 9600 baud, 8N1
7. standalone Python test
8. only after the standalone test succeeds, troubleshoot the CraftBeerPi plugin
