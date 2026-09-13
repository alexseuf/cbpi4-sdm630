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
    # Derived trip-counter values. They are the difference between the current
    # cumulative SDM630 energy registers and a persistent reset baseline.
    "Kurzzeitzähler Bezug": {"derived": "trip_import", "decimals": 3},
    "Kurzzeitzähler Einspeisung": {"derived": "trip_export", "decimals": 3},
}

PARITY = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
}

COUNTER_FILE = Path.home() / ".craftbeerpi4-sdm630" / "short_term_counters.json"


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

    for path in sorted(glob.glob("/dev/serial/by-id/*")):
        add_path(path)
    for path in ("/dev/serial0", "/dev/serial1"):
        add_path(path)
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*"):
        for path in sorted(glob.glob(pattern)):
            add_path(path)
    for pattern in ("/dev/ttyAMA*", "/dev/ttyS*"):
        for path in sorted(glob.glob(pattern)):
            add_path(path)

    if not ports:
        ports.append("/dev/ttyUSB0")

    return ports


SERIAL_PORT_OPTIONS = _get_serial_ports()
DEFAULT_PORT = SERIAL_PORT_OPTIONS[0]

_bus_locks: Dict[str, asyncio.Lock] = {}
_counter_lock = asyncio.Lock()
_counter_state_loaded = False
_counter_state = {"version": 1, "meters": {}}


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


def _counter_key(port: str, slave: int) -> str:
    return f"{port}|{slave}"


def _load_counter_state_sync():
    global _counter_state_loaded, _counter_state
    if _counter_state_loaded:
        return

    try:
        if COUNTER_FILE.exists():
            with COUNTER_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("meters"), dict):
                _counter_state = data
    except Exception as e:
        logger.warning("SDM630: short-term counter state could not be loaded from %s: %s",
                       COUNTER_FILE, e)

    _counter_state_loaded = True


def _save_counter_state_sync():
    try:
        COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = COUNTER_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(_counter_state, f, separators=(",", ":"))
        os.replace(tmp, COUNTER_FILE)
    except Exception as e:
        logger.warning("SDM630: short-term counter state could not be saved to %s: %s",
                       COUNTER_FILE, e)


def _get_short_term_values_sync(port: str, slave: int, import_kwh: float,
                                export_kwh: float):
    _load_counter_state_sync()
    key = _counter_key(port, slave)
    meter = _counter_state["meters"].get(key)

    # First use: start the short-term counters at zero.
    if not isinstance(meter, dict):
        meter = {
            "import_base": import_kwh,
            "export_base": export_kwh,
            "reset_time": time.time(),
        }
        _counter_state["meters"][key] = meter
        _save_counter_state_sync()

    # If the SDM630 itself was reset or replaced, use the new cumulative values
    # as the new baseline so no negative trip-counter value can occur.
    if (import_kwh + 1e-6 < float(meter.get("import_base", import_kwh)) or
            export_kwh + 1e-6 < float(meter.get("export_base", export_kwh))):
        meter["import_base"] = import_kwh
        meter["export_base"] = export_kwh
        meter["reset_time"] = time.time()
        _save_counter_state_sync()

    trip_import = max(0.0, import_kwh - float(meter["import_base"]))
    trip_export = max(0.0, export_kwh - float(meter["export_base"]))
    return trip_import, trip_export


def _reset_short_term_sync(port: str, slave: int, import_kwh: float,
                           export_kwh: float):
    _load_counter_state_sync()
    key = _counter_key(port, slave)
    _counter_state["meters"][key] = {
        "import_base": import_kwh,
        "export_base": export_kwh,
        "reset_time": time.time(),
    }
    _save_counter_state_sync()


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

        async with _counter_lock:
            trip_import, trip_export = await asyncio.to_thread(
                _get_short_term_values_sync,
                port,
                slave,
                values["Energie Bezug"],
                values["Energie Einspeisung"],
            )

        values["Kurzzeitzähler Bezug"] = trip_import
        values["Kurzzeitzähler Einspeisung"] = trip_export

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

    @action("Kurzzeitzähler nullen", parameters=[])
    async def reset_short_term_counters(self, **kwargs):
        """Reset both short-term energy counters for this SDM630."""
        lock = _bus_locks.setdefault(self.port, asyncio.Lock())
        async with lock:
            values = await asyncio.to_thread(
                _read_all_sync,
                self.port,
                self.slave,
                self.baudrate,
                self.parity,
                self.stopbits,
                self.timeout,
            )
            async with _counter_lock:
                await asyncio.to_thread(
                    _reset_short_term_sync,
                    self.port,
                    self.slave,
                    values["Energie Bezug"],
                    values["Energie Einspeisung"],
                )

            # Invalidate all cached reads for this physical meter so the new
            # zero value becomes visible immediately on the next refresh.
            for cache_key, entry in _cache.items():
                if cache_key[0] == self.port and cache_key[1] == self.slave:
                    entry.timestamp = 0.0
                    entry.values = {}

        if self.measurement in ("Kurzzeitzähler Bezug", "Kurzzeitzähler Einspeisung"):
            self.value = 0.0
            self.push_update(self.value)
            self.log_data(self.value)

        logger.info("SDM630 short-term counters reset on %s slave %s",
                    self.port, self.slave)

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
