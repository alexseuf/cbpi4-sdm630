# USB/RS485 adapter – buying sources

The tested adapter for this project is the **FTDI USB-RS485-WE-1800-BT** (1.8 m, FT232R/FT232RQ based). It provides a direct wired Modbus RTU connection between the Raspberry Pi and the SDM630.

Prices and availability change frequently. The values below are examples checked in September 2026 and should be verified before ordering.

| Supplier / product | Approx. price | Notes |
|---|---:|---|
| Mouser – FTDI USB-RS485-WE-1800-BT | ~29.00 EUR | Original FTDI 1.8 m cable; in stock when checked |
| Farnell – FTDI USB-RS485-WE-1800-BT | ~33.91 EUR + VAT | Original FTDI 1.8 m cable; in stock when checked |
| RS – FTDI USB-RS485-WE-1800-BT | ~42.45 EUR incl. VAT | Original FTDI 1.8 m cable; in stock when checked |
| Reichelt – DIGITUS DA-70157 | ~15.50 EUR incl. VAT | Lower-cost FTDI/FT232RL USB-to-RS485 alternative with screw terminals; Linux support stated by supplier |
| Reichelt – EXSYS EX-13102 | ~18.90 EUR incl. VAT | FTDI USB-to-RS485 converter board; lower-cost alternative, wiring differs from USB-RS485-WE |

Links:

- Mouser: https://www.mouser.de/en/ProductDetail/FTDI/USB-RS485-WE-1800-BT
- Farnell: https://de.farnell.com/en-DE/ftdi/usb-rs485-we-1800-bt/cable-usb-rs485-serial-converter/dp/1740357
- RS: https://de.rs-online.com/web/p/schnittstellenadapter-und-konverter/6877834
- Reichelt DIGITUS DA-70157: https://www.reichelt.com/de/en/shop/product/usb_2_0_serial_rs485_converter-122187
- Reichelt USB/RS485 converter selection: https://www.reichelt.de/de/de/shop/kategorie/exsys/usb-konverter-6908

## Recommendation

For the documented/tested wiring, use the **original FTDI USB-RS485-WE-1800-BT**. It matches the wire-colour table and photographs in the main README.

Cheaper USB-to-RS485 adapters can also work with the plugin if Linux exposes them as a serial device such as `/dev/ttyUSB0` or `/dev/serial/by-id/...`. However, their terminal and wire assignments can be different. Do **not** apply the orange/yellow FTDI wire-colour mapping to another adapter without checking its documentation.

For permanent installations, prefer an adapter with a genuine, well-supported USB/serial chipset and a stable `/dev/serial/by-id/...` identifier. Very cheap no-name adapters may work but can use different chipsets or change hardware revisions without notice.
