# cbpi4-sdm630

CraftBeerPi 4 plugin for an Eastron SDM630 connected via Modbus RTU and a USB/RS485 adapter.

## Measurements

The plugin provides a CraftBeerPi sensor type named `SDM630 Power`. Create four sensor instances to display:

- Leistung L1: SDM630 input register 30013 / PDU address 12
- Leistung L2: SDM630 input register 30015 / PDU address 14
- Leistung L3: SDM630 input register 30017 / PDU address 16
- Gesamtleistung: SDM630 input register 30053 / PDU address 52

Values are active power in watts. The registers are read as 32-bit floating point values with Modbus function code 04.

## Tested hardware settings

This repository was initially tested with:

- SDM630 Modbus address: 1
- Baudrate: 9600
- Data format: 8N1
- USB/RS485 adapter: FTDI FT232R
- Stable Linux device path: `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0`

The serial settings and device path remain configurable in CraftBeerPi.

## Installation

On a CraftBeerPi 4 installation managed with pipx:

```bash
git clone https://github.com/alexseuf/cbpi4-sdm630.git
cd cbpi4-sdm630
pipx runpip cbpi4 install .
```

Then restart CraftBeerPi.

## CraftBeerPi configuration

Create four hardware sensors of type `SDM630 Power`:

1. `SDM630 L1` with `Messwert = Leistung L1`
2. `SDM630 L2` with `Messwert = Leistung L2`
3. `SDM630 L3` with `Messwert = Leistung L3`
4. `SDM630 Gesamt` with `Messwert = Gesamtleistung`

Use identical Port, Slave, Baudrate, Parity and Stopbits settings for all four.

The plugin uses a shared asynchronous lock and a short-lived cache. Therefore four CraftBeerPi sensor instances do not try to access the same USB/RS485 adapter simultaneously.

## Typical settings

- Port: `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0`
- Slave: `1`
- Baudrate: `9600`
- Parity: `N`
- Stopbits: `1`
- Interval: `2 s`
- Timeout: `0.5 s`

If communication fails, verify RS485 A/B polarity, Modbus address, baudrate, parity, stopbits and serial-device permissions.
