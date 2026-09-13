# cbpi4-sdm630

CraftBeerPi 4 plugin for an Eastron SDM630 connected via Modbus RTU and a USB/RS485 adapter.

## Official Eastron Modbus documentation

Official manufacturer documentation:

**Eastron SDM630Modbus Smart Meter – Modbus Protocol Implementation V1.8**

https://www.eastroneurope.com/images/uploads/products/protocol/SDM630_MODBUS_Protocol.pdf

A repository-local description of the exact registers used by this plugin is available here:

[SDM630 Modbus reference – registers used by this plugin](docs/SDM630_MODBUS_REFERENCE.md)

## Measurements

The plugin provides a CraftBeerPi sensor type named `SDM630 Power`. Multiple sensor instances can be created, each selecting one SDM630 measurement.

Direct SDM630 values:

- Gesamtleistung: register 30053 / PDU address 52, W
- Leistung L1: register 30013 / PDU address 12, W
- Leistung L2: register 30015 / PDU address 14, W
- Leistung L3: register 30017 / PDU address 16, W
- Spannung L1: register 30001 / PDU address 0, V L-N
- Spannung L2: register 30003 / PDU address 2, V L-N
- Spannung L3: register 30005 / PDU address 4, V L-N
- Strom L1: register 30007 / PDU address 6, A
- Strom L2: register 30009 / PDU address 8, A
- Strom L3: register 30011 / PDU address 10, A
- Energie Bezug: register 30073 / PDU address 72, kWh
- Energie Einspeisung: register 30075 / PDU address 74, kWh

Derived values calculated by the plugin:

- Kurzzeitzähler Bezug: imported energy since the last manual reset, kWh
- Kurzzeitzähler Einspeisung: exported energy since the last manual reset, kWh

The short-term counters work like a trip counter in a vehicle. The SDM630 cumulative energy registers themselves are never reset. Instead, the plugin stores the current import/export counter readings as a baseline and displays the difference from that baseline.

## Resetting the short-term counters

The sensor type provides the CraftBeerPi action:

`Kurzzeitzähler nullen`

This action resets **both** short-term counters together:

- Kurzzeitzähler Bezug → 0.000 kWh
- Kurzzeitzähler Einspeisung → 0.000 kWh

The underlying SDM630 total energy counters remain unchanged.

The reset baseline is stored persistently in:

```text
~/.craftbeerpi4-sdm630/short_term_counters.json
```

Therefore the short-term counters survive CraftBeerPi restarts and Raspberry Pi reboots.

The state is kept separately for every combination of serial port and Modbus slave address.

In the CraftBeerPi dashboard, sensor actions can be enabled for a SensorData widget. The widget then shows its action menu, where `Kurzzeitzähler nullen` can be selected.

## Data format

The direct SDM630 registers are read as:

- Modbus Function Code 04 – Read Input Registers
- IEEE-754 Float32
- two 16-bit Modbus registers per value
- big-endian register order

Display rounding:

- power: 1 decimal place
- voltage: 1 decimal place
- current: 2 decimal places
- energy: 3 decimal places

## CraftBeerPi default handling

CraftBeerPi 4.7.x does not visibly prefill all plugin properties when a new sensor is created. This plugin follows the common approach used by established CBPi plugins: empty properties are accepted and sensible defaults are applied internally by the plugin.

If a field is left empty, the plugin uses:

- Port: first detected serial interface, with `/dev/serial/by-id/...` preferred
- Slave: `1`
- Baudrate: `9600`
- Parity: `N`
- Stopbits: `1`
- Messwert: `Gesamtleistung`
- Intervall: `2 s`
- Timeout: `0.5 s`

The CraftBeerPi descriptions also show these defaults as `leer = ...`.

## Tested hardware settings

This repository was initially tested with:

- SDM630 Modbus address: 1
- Baudrate: 9600
- Data format: 8N1
- USB/RS485 adapter: FTDI FT232R
- Stable Linux device path: `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0`

The serial settings and device path remain configurable in CraftBeerPi.

## Installation

On a CraftBeerPi 4 installation managed with pipx, install directly from GitHub:

```bash
pipx runpip cbpi4 install https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
```

Then restart CraftBeerPi:

```bash
sudo systemctl restart craftbeerpi.service
```

## Updating the plugin

To update an already installed version to the newest version from the `main` branch, run:

```bash
pipx runpip cbpi4 install --upgrade https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
```

Then restart CraftBeerPi:

```bash
sudo systemctl restart craftbeerpi.service
```

Check the installed package version with:

```bash
pipx runpip cbpi4 show cbpi4-sdm630
```

If pip reports that the same version is already installed but the repository contains newer code, force a reinstall with:

```bash
pipx runpip cbpi4 install --upgrade --force-reinstall https://github.com/alexseuf/cbpi4-sdm630/archive/main.zip
```

A complete step-by-step description of the tested Raspberry Pi setup, the CraftBeerPi service/restart commands, FTDI wiring and the standalone RS485/Modbus test is available here:

[Installation and RS485 test](docs/INSTALLATION_AND_RS485_TEST.md)

## CraftBeerPi configuration

Create one hardware sensor of type `SDM630 Power` for every value you want to display. For example:

1. `SDM630 L1 Leistung` with `Messwert = Leistung L1`
2. `SDM630 L2 Leistung` with `Messwert = Leistung L2`
3. `SDM630 L3 Leistung` with `Messwert = Leistung L3`
4. `SDM630 Gesamtleistung` with `Messwert = Gesamtleistung`
5. `SDM630 Spannung L1` with `Messwert = Spannung L1`
6. `SDM630 Spannung L2` with `Messwert = Spannung L2`
7. `SDM630 Spannung L3` with `Messwert = Spannung L3`
8. `SDM630 Strom L1` with `Messwert = Strom L1`
9. `SDM630 Strom L2` with `Messwert = Strom L2`
10. `SDM630 Strom L3` with `Messwert = Strom L3`
11. `SDM630 Bezug gesamt` with `Messwert = Energie Bezug`
12. `SDM630 Einspeisung gesamt` with `Messwert = Energie Einspeisung`
13. `SDM630 Kurzzeit Bezug` with `Messwert = Kurzzeitzähler Bezug`
14. `SDM630 Kurzzeit Einspeisung` with `Messwert = Kurzzeitzähler Einspeisung`

Use identical Port, Slave, Baudrate, Parity and Stopbits settings for all sensor instances belonging to the same SDM630.

The plugin uses a shared asynchronous lock and a short-lived cache. Therefore multiple CraftBeerPi sensor instances do not try to access the same USB/RS485 adapter simultaneously.

## Typical settings

- Port: `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0`
- Slave: `1`
- Baudrate: `9600`
- Parity: `N`
- Stopbits: `1`
- Interval: `2 s`
- Timeout: `0.5 s`

If communication fails, verify RS485 A/B polarity, Modbus address, baudrate, parity, stopbits and serial-device permissions.
