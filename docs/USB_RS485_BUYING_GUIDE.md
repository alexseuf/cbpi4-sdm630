# USB/RS485 adapter – buying sources

The tested adapter for this project is an **FTDI-style USB-RS485-WE cable** with open wire ends. The AliExpress FT232RQ cable marked below is the cable used in the documented/tested setup. It provides a direct wired Modbus RTU connection between the Raspberry Pi and the SDM630.

Prices and availability change frequently. The values below are examples checked in September 2026 and should be verified before ordering. Chip information for marketplace products is based on the seller listing and does not guarantee that the IC is a genuine FTDI device.

| Supplier / product | Approx. price | Notes |
|---|---:|---|
| Mouser – FTDI USB-RS485-WE-1800-BT | ~29.00 EUR | Original FTDI 1.8 m cable |
| Farnell – FTDI USB-RS485-WE-1800-BT | ~33.91 EUR + VAT | Original FTDI 1.8 m cable |
| RS – FTDI USB-RS485-WE-1800-BT | ~42.45 EUR incl. VAT | Original FTDI 1.8 m cable |
| AliExpress – USB to RS-485-WE, 6-pin / open wire ends, item 1005012108870590 | ~US$21 | FT232RL stated by seller; construction similar to the original FTDI USB-RS485-WE |
| **AliExpress – USB to 6-core open wire end, compatible USB-RS485-WE-1800-BT, item 1005003726423806** | **~US$9.75** | **FT232RQ stated by seller; this is the cable used for this project/tested setup** |
| Reichelt – DIGITUS DA-70157 | ~15.50 EUR incl. VAT | Lower-cost FTDI/FT232RL USB-to-RS485 alternative with screw terminals; Linux support stated by supplier |
| Reichelt – EXSYS EX-13102 | ~18.90 EUR incl. VAT | FTDI USB-to-RS485 converter board; lower-cost alternative, wiring differs from USB-RS485-WE |

Links:

- Mouser: https://www.mouser.de/en/ProductDetail/FTDI/USB-RS485-WE-1800-BT
- Farnell: https://de.farnell.com/en-DE/ftdi/usb-rs485-we-1800-bt/cable-usb-rs485-serial-converter/dp/1740357
- RS: https://de.rs-online.com/web/p/schnittstellenadapter-und-konverter/6877834
- AliExpress FT232RL, item 1005012108870590: https://www.aliexpress.com/item/1005012108870590.html
- **AliExpress FT232RQ – cable used in this project, item 1005003726423806:** https://www.aliexpress.com/item/1005003726423806.html
- Reichelt DIGITUS DA-70157: https://www.reichelt.com/de/en/shop/product/usb_2_0_serial_rs485_converter-122187
- Reichelt USB/RS485 converter selection: https://www.reichelt.de/de/de/shop/kategorie/exsys/usb-konverter-6908

## Recommendation

The **AliExpress FT232RQ cable, item 1005003726423806, is the cable used in the documented setup for this project**. Its USB-RS485-WE-style construction with open wire ends is particularly convenient for direct connection to the SDM630 terminals.

The genuine FTDI USB-RS485-WE-1800-BT is the manufacturer-branded alternative. Marketplace listings can change over time, and the FT232RQ/FT232RL chip description is supplied by the seller. A low price alone should not be taken as proof that a genuine FTDI IC is fitted.

Other USB-to-RS485 adapters can also work with the plugin if Linux exposes them as a serial device such as `/dev/ttyUSB0` or `/dev/serial/by-id/...`. However, their terminal and wire assignments can be different. Do **not** apply the orange/yellow wire-colour mapping to another adapter without checking its documentation.

For permanent installations, prefer an adapter with a well-supported USB/serial chipset and a stable `/dev/serial/by-id/...` identifier. Very cheap no-name adapters may work but can use different chipsets or change hardware revisions without notice.
