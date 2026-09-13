# Eastron SDM630 Modbus – verwendete Register

## Offizielle Dokumentation

Offizielle Eastron-Dokumentation:

**Eastron SDM630Modbus Smart Meter – Modbus Protocol Implementation V1.8**

https://www.eastroneurope.com/images/uploads/products/protocol/SDM630_MODBUS_Protocol.pdf

Die vollständige PDF bleibt beim Hersteller verlinkt. In diesem Repository wird bewusst nur die für dieses Plugin benötigte Registerauswahl dokumentiert.

## Datenformat

Die von diesem Plugin verwendeten Messwerte liegen in den **Input Registers (3X)** des SDM630.

- Modbus Function Code: **04 – Read Input Registers**
- Datenformat: **IEEE-754 Float32**
- Jeder Messwert belegt **2 aufeinanderfolgende 16-Bit-Modbus-Register**
- Das Plugin verwendet die **0-basierte Modbus-PDU-Startadresse**
- Standard-Registerreihenfolge: höchstwertiges Register zuerst (`BYTEORDER_BIG`)

Beispiel: Das Herstellerregister `30013` entspricht der 0-basierten PDU-Adresse `12` (`0x000C`).

## Vom Plugin direkt verwendete Register

| CraftBeerPi Messwert | Eastron Register | PDU-Adresse (dez.) | PDU-Adresse (hex) | Einheit | Beschreibung laut Eastron |
|---|---:|---:|---:|---|---|
| Spannung L1 | 30001 | 0 | 0x0000 | V | Phase 1 line to neutral volts |
| Spannung L2 | 30003 | 2 | 0x0002 | V | Phase 2 line to neutral volts |
| Spannung L3 | 30005 | 4 | 0x0004 | V | Phase 3 line to neutral volts |
| Strom L1 | 30007 | 6 | 0x0006 | A | Phase 1 current |
| Strom L2 | 30009 | 8 | 0x0008 | A | Phase 2 current |
| Strom L3 | 30011 | 10 | 0x000A | A | Phase 3 current |
| Leistung L1 | 30013 | 12 | 0x000C | W | Phase 1 power |
| Leistung L2 | 30015 | 14 | 0x000E | W | Phase 2 power |
| Leistung L3 | 30017 | 16 | 0x0010 | W | Phase 3 power |
| Gesamtleistung | 30053 | 52 | 0x0034 | W | Total system power |
| Energie Bezug | 30073 | 72 | 0x0048 | kWh | Total Import kWh |
| Energie Einspeisung | 30075 | 74 | 0x004A | kWh | Total Export kWh |

## Abgeleitete 24-h-Werte

Der SDM630 besitzt **keine eigenen Register für die Energie der letzten 24 Stunden**. Deshalb berechnet das Plugin diese Werte aus den fortlaufenden Gesamtzählern:

- `Bezug 24 h = Energie Bezug jetzt - Energie Bezug vor 24 h`
- `Einspeisung 24 h = Energie Einspeisung jetzt - Energie Einspeisung vor 24 h`

Dazu werden die beiden Register `30073` und `30075` ungefähr einmal pro Minute historisch gespeichert. Das Plugin hält etwa 26 Stunden Historie vor und interpoliert den Zählerstand an der 24-Stunden-Grenze zwischen den benachbarten Samples.

Persistente Historie:

```text
~/.craftbeerpi4-sdm630/energy_history.json
```

Nach einem Neustart von CraftBeerPi wird diese Datei wieder eingelesen. Ein echter 24-h-Wert steht erst zur Verfügung, wenn mindestens 24 Stunden Historie gesammelt wurden; vorher liefert der jeweilige 24-h-Sensor `0.000 kWh`.

Wenn ein Rücksprung eines Energiezählers erkannt wird, beispielsweise nach Zähler-Reset oder Geräteaustausch, beginnt die 24-h-Historie für diesen Zähler neu.

## Zuordnung im Plugin

Die direkt gelesenen Register und die beiden abgeleiteten Werte stehen in `cbpi4-sdm630/__init__.py` in `MEASUREMENTS`.

```python
MEASUREMENTS = {
    "Gesamtleistung": {"address": 52, "decimals": 1},
    "Leistung L1": {"address": 12, "decimals": 1},
    "Leistung L2": {"address": 14, "decimals": 1},
    "Leistung L3": {"address": 16, "decimals": 1},
    "Spannung L1": {"address": 0, "decimals": 1},
    "Spannung L2": {"address": 2, "decimals": 1},
    "Spannung L3": {"address": 4, "decimals": 1},
    "Strom L1": {"address": 6, "decimals": 2},
    "Strom L2": {"address": 8, "decimals": 2},
    "Strom L3": {"address": 10, "decimals": 2},
    "Energie Bezug": {"address": 72, "decimals": 3},
    "Energie Einspeisung": {"address": 74, "decimals": 3},
    "Bezug 24 h": {"derived": "import_24h", "decimals": 3},
    "Einspeisung 24 h": {"derived": "export_24h", "decimals": 3},
}
```

## Hinweise zu Import und Export

Laut Eastron ist:

- `30073` = **Total Import kWh** → im Plugin `Energie Bezug`
- `30075` = **Total Export kWh** → im Plugin `Energie Einspeisung`

Zusätzlich führt der SDM630 bei neueren Registertabellen phasenweise Energiezähler, z. B. L1/L2/L3 Import und Export. Diese werden vom Plugin derzeit **nicht** verwendet.

## Quelle

Registerbezeichnungen, Adressen, Einheiten und Modbus-Datenformat basieren auf der offiziellen Eastron-Dokumentation **SDM630Modbus Smart Meter – Modbus Protocol Implementation V1.8**. Für die vollständige Registertabelle und weitere Hinweise ist immer die Hersteller-PDF maßgeblich.
