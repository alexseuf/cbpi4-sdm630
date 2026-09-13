# -*- coding: utf-8 -*-
import asyncio
import glob
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

import minimalmodbus
import serial
from cbpi.api import *

logger = logging.getLogger(__name__)

# Eastron SDM630 input registers, 0-based Modbus PDU addresses.
# Default handling follows the common CBPi plugin pattern: the UI may leave
# properties empty, so sensible defaults are applied in __init__ via _prop().
MEASUREMENTS = {
    "Gesamtleistung": {"address": 52, "decimals": 1},   # 30053, W
    "Leistung L1": {"address": 12, "decimals": 1},     # 30013, W
    "Leistung L2": {"address": 14, "decimals": 1},     # 30015, W
    "Leistung L3": {"address": 16, "decimals": 1},     # 30017, W
    "Spannung L1": {"address": 0, "decimals": 1},      # 30001, V L-N
    "Spannung L2": {"address": 2, "decimals": 1},      # 30003, V L-N
    "Spannung L3": {"address": 4, "decimals": 1},      # 30005, V L-N
    "Strom L1": {"address": 6, "decimals": 2},         # 30007, A
    "Strom L2": {"address": 8, "decimals": 2},         # 30009, A
    "Strom L3": {"address": 10, "decimals": 2},        # 30011, A
    "Energie Bezug": {"address": 72, "decimals": 3},   # 30073, kWh import
    "Energie Einspeisung": {"address": 74, "decimals": 3},  # 30075, kWh export
    # Derived values calculated from the cumulative energy registers above.
    "Bezug 24 h": {"derived": "import_24h", "decimals": 3},
    "Einspeisung 24 h": {"derived": "export_24h", "decimals": 3},
}

PARITY = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
}

# The SDM630 has no native "last 24 h" register. The plugin stores one
# import/export counter sample per minute and keeps enough history to calculate
# a rolling 24-hour difference. The history survives CraftBeerPi restarts.
HISTORY_SAMPLE_INTERVAL = 60.0
HISTORY_RETENTION = 26 * 60 * 60
HISTORY_WINDOW = 24 * 60 * 60
HISTORY_FILE = Path.home() / ".craftbeerpi4-sdm630" / "energy_history.json"


def _get_serial_ports():
    """Return active serial ports.

    Stable /dev/serial/by-id paths are preferred for USB adapters. In addition,
    Raspberry Pi internal UARTs are offered when present, including /dev/serial0,
    /dev/serial1, /dev/ttyAMA* and /dev/ttyS*.

    Aliases that point to a device already listed are suppressed so the same
    physical UART normally appears only once.
    """
    ports = []
    represented_devices = set()

    def add_path(path):
        if not os.path.exists(path):
            return
        real_path = os.path.realpath(path)
        if real_path in represented_devices:
            return
        ports.append(path)
        represented_devices.add(real_path)

    # 1) Stable USB serial names are best for USB/RS485 adapters.
    for path in sorted(glob.glob("/dev/serial/by-id/*")):
        add_path(path)

    # 2) Raspberry Pi stable aliases for onboard UARTs.
    for path in ("/dev/serial0", "/dev/serial1"):
        add_path(path)

    # 3) USB serial adapters without a by-id entry.
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*"):
        for path in sorted(glob.glob(pattern)):
            add_path(path)

    # 4) Direct onboard UART device nodes.
    for pattern in ("/dev/ttyAMA*", "/dev/ttyS*"):
        for path in sorted(glob.glob(pattern)):
            add_path(path)

    if not ports:
        ports.append("/dev/ttyUSB0")

    return ports


SERIAL_PORT_OPTIONS = _get_serial_ports()
DEFAULT_PORT = SERIAL_PORT_OPTIONS[0]

_bus_locks: Dict[str, asyncio.Lock] = {}
_history_lock = asyncio.Lock()
_history_loaded = False
_history = {"version": 1, "meters": {}}


@dataclass
class _CacheEntry:
    timestamp: float = 0.0
    values: Dict[str, float] = field(default_factory=dict)


_cache: Dict[Tuple[str, int, int, str, int], _CacheEntry] = {}


def _prop(props, name, default):
    """Return a CBPi property value, falling back for missing/empty values."""
    value = props.get(name, default)
    if value is None or value == "":
        return default
    return value


def _history_key(port: str, slave: int) -> str:
    return f"{port}|{slave}"


def _load_history_sync():
    global _history_loaded, _history
    if _history_loaded:
        return

    try:
        if HISTORY_FILE.exists():
            with HISTORY_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("meters"), dict):
                _history = data
    except Exception as e:
        logger.warning("SDM630: energy history could not be loaded from %s: %s",
                       HISTORY_FILE, e)

    _history_loaded = True


def _save_history_sync():
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = HISTORY_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(_history, f, separators=(",", ":"))
        os.replace(tmp, HISTORY_FILE)
    except Exception as e:
        logger.warning("SDM630: energy history could not be saved to %s: %s",
                       HISTORY_FILE, e)


def _counter_at(samples, field, target_ts):
    """Interpolate a cumulative counter at target_ts from stored samples."""
    if not samples or float(samples[0]["t"]) > target_ts:
        return None

    previous = samples[0]
    for current in samples[1:]:
        if float(current["t"]) >= target_ts:
            dt = float(current["t"]) - float(previous["t"])
            if dt <= 0:
                return float(previous[field])
            fraction = (target_ts - float(previous["t"])) / dt
            return float(previous[field]) + fraction * (
                float(current[field]) - float(previous[field])
            )
        previous = current

    return float(previous[field])


def _update_history_sync(port: str, slave: int, import_kwh: float,
                         export_kwh: float, now_wall: float):
    _load_history_sync()
    key = _history_key(port, slave)
    samples = _history["meters"].setdefault(key, [])

    # If the SDM630 counter was reset or the meter was replaced, start a new
    # history period instead of reporting a negative 24-hour value.
    if samples:
        last = samples[-1]
        if (import_kwh + 1e-6 < float(last["import"]) or
                export_kwh + 1e-6 < float(last["export"])):
            logger.warning("SDM630: energy counter reset detected for %s; "
                           "24 h history starts again", key)
            samples.clear()

    should_store = (
        not samples or
        (now_wall - float(samples[-1]["t"])) >= HISTORY_SAMPLE_INTERVAL
    )

    if should_store:
        samples.append({
            "t": now_wall,
            "import": import_kwh,
            "export": export_kwh,
        })

        # Keep one sample before the retention boundary for interpolation.
        cutoff = now_wall - HISTORY_RETENTION
        while len(samples) > 1 and float(samples[1]["t"]) < cutoff:
            samples.pop(0)

        _save_history_sync()

    target = now_wall - HISTORY_WINDOW
    base_import = _counter_at(samples, "import", target)
    base_export = _counter_at(samples, "export", target)

    # A genuine rolling 24-hour value only exists after 24 hours of history.
    import_24h = 0.0 if base_import is None else max(0.0, import_kwh - base_import)
    export_24h = 0.0 if base_export is None else max(0.0, export_kwh - base_export)

    return import_24h, export_24h


def _read_all_sync(port: str, slave: int, baudrate: int, parity: str,
                   stopbits: int, timeout: float):
    instrument = minimalmodbus.Instrument(port, slave, mode=minimalmodbus.MODE_RTU)
    try:
        instrument.serial.baudrate = baudrate
        instrument.serial.bytesize = 8
        instrument.serial.parity = PARITY.get(parity, serial.PARITY_NONE)
        instrument.serial.stopbits = stopbits
        instrument.serial.timeout = timeout
        instrument.clear_buffers_before_each_transaction = True
        instrument.close_port_after_each_call = False

        values = {}
        for name, cfg in MEASUREMENTS.items():
            if "address" not in cfg:
                continue
            values[name] = float(instrument.read_float(
                registeraddress=cfg["address"],
                functioncode=4,
                number_of_registers=2,
                byteorder=minimalmodbus.BYTEORDER_BIG,
            ))
        return values
    finally:
        try:
            instrument.serial.close()
        except Exception:
            pass


async def _get_values(port, slave, baudrate, parity, stopbits, timeout, cache_time):
    key = (port, slave, baudrate, parity, stopbits)
    lock = _bus_locks.setdefault(port, asyncio.Lock())
    entry = _cache.setdefault(key, _CacheEntry())

    now = time.monotonic()
    if entry.values and (now - entry.timestamp) < cache_time:
        return entry.values

    async with lock:
        now = time.monotonic()
        if entry.values and (now - entry.timestamp) < cache_time:
            return entry.values

        values = await asyncio.to_thread(
            _read_all_sync, port, slave, baudrate, parity, stopbits, timeout
        )

        async with _history_lock:
            import_24h, export_24h = await asyncio.to_thread(
                _update_history_sync,
                port,
                slave,
                values["Energie Bezug"],
                values["Energie Einspeisung"],
                time.time(),
            )

        values["Bezug 24 h"] = import_24h
        values["Einspeisung 24 h"] = export_24h

        entry.values = values
        entry.timestamp = time.monotonic()
        return values


@parameters([
    Property.Select(label="Port", options=SERIAL_PORT_OPTIONS,
                    description="Serielle Schnittstelle; /dev/serial/by-id und Raspberry-Pi-UARTs werden automatisch erkannt"),
    Property.Number(label="Slave", configurable=True, default_value=1,
                    description="Modbus-Adresse des SDM630 (leer = 1)"),
    Property.Select(label="Baudrate", options=[9600, 2400, 4800, 19200, 38400],
                    description="Modbus-Baudrate (leer = 9600)"),
    Property.Select(label="Parity", options=["N", "E", "O"],
                    description="Paritaet (leer = N)"),
    Property.Select(label="Stopbits", options=[1, 2],
                    description="Stopbits (leer = 1)"),
    Property.Select(label="Messwert", options=list(MEASUREMENTS.keys()),
                    description="Anzuzeigender Messwert (leer = Gesamtleistung)"),
    Property.Select(label="Intervall", options=[2, 1, 5, 10, 30, 60],
                    description="Aktualisierungsintervall in Sekunden (leer = 2 s)"),
    Property.Number(label="Timeout", configurable=True, default_value=0.5,
                    description="Serieller Timeout in Sekunden (leer = 0.5 s)"),
])
class SDM630PowerSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(SDM630PowerSensor, self).__init__(cbpi, id, props)
        self.value = 0.0
        self.port = str(_prop(self.props, "Port", DEFAULT_PORT))
        self.slave = int(float(_prop(self.props, "Slave", 1)))
        self.baudrate = int(_prop(self.props, "Baudrate", 9600))
        self.parity = str(_prop(self.props, "Parity", "N"))
        self.stopbits = int(_prop(self.props, "Stopbits", 1))
        self.measurement = str(_prop(self.props, "Messwert", "Gesamtleistung"))
        self.interval = float(_prop(self.props, "Intervall", 2))
        self.timeout = float(_prop(self.props, "Timeout", 0.5))
        if self.measurement not in MEASUREMENTS:
            self.measurement = "Gesamtleistung"

    async def run(self):
        cache_time = max(0.2, self.interval * 0.8)
        while self.running:
            try:
                values = await _get_values(
                    self.port, self.slave, self.baudrate, self.parity,
                    self.stopbits, self.timeout, cache_time
                )
                decimals = MEASUREMENTS[self.measurement]["decimals"]
                self.value = round(float(values[self.measurement]), decimals)
                self.push_update(self.value)
                self.log_data(self.value)
            except Exception as e:
                logger.error("SDM630 read error on %s slave %s (%s): %s",
                             self.port, self.slave, self.measurement, e)
            await asyncio.sleep(self.interval)

    def get_state(self):
        return dict(value=self.value)


def setup(cbpi):
    cbpi.plugin.register("SDM630 Power", SDM630PowerSensor)
