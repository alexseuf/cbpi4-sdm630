# FTDI USB-RS485-WE adapter

The SDM630 test setup uses an FTDI USB-RS485-WE / FT232R based USB-to-RS485 cable.

## Wiring

According to the FTDI USB-RS485-WE pinout:

| Wire | Function | Connection for SDM630 |
|---|---|---|
| Orange | Data+ / A | RS485 A / + |
| Yellow | Data- / B | RS485 B / - |
| Black | GND | optional signal GND |
| Red | +5 V output | not required for SDM630 RS485 |
| Brown | internal 120 ohm termination, pin 1 | only for bus termination |
| Green | internal 120 ohm termination, pin 2 | only for bus termination |

Brown and green are the two ends of the cable's internal 120 ohm termination resistor. If this adapter is located at the physical end of the RS485 bus, the internal termination can be placed across A/B by connecting the termination wires accordingly. Otherwise leave brown and green unconnected.

## Tested Linux identification

```text
/dev/ttyUSB0
/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0
```

The `/dev/serial/by-id/...` name is preferred in the CraftBeerPi configuration because it normally remains stable after reboot or reconnecting USB devices.

## Reference images

Useful reference pictures showing the cable and its wire assignment:

- FTDI datasheet pinout image via DigiKey: https://www.digikey.lv/htmldatasheets/production/647732/0/0/1/usb-rs485-we-5000-bt.html
- Product/wire photo: https://usangreencable.com/products/ftdi-ft232rq-usb-to-rs485-serial-converter-cable-6p-ftdi-chip-6-pins-wire-end-we

These are external reference images and are linked rather than copied into this repository to avoid republishing third-party copyrighted product photography.

## Purchasing / AliExpress

Search AliExpress for the exact terms:

`FTDI USB-RS485-WE-1800-BT`

or

`FT232R USB RS485 WE cable`

When selecting an inexpensive compatible cable, verify the following before purchase:

- RS485, not a TTL-only FT232 cable
- automatic half-duplex direction control
- Linux support
- A/B connections clearly documented
- preferably FTDI FT232R/FT232RL or an explicitly compatible chipset

A product merely containing an FT232 chip is not automatically equivalent to the USB-RS485-WE; many FT232 listings are USB-to-TTL rather than USB-to-RS485.
