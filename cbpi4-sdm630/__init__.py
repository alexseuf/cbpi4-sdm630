# -*- coding: utf-8 -*-
import asyncio
import glob
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple

import minimalmodbus
import serial
from cbpi.api import *

logger = logging.getLogger(__name__)

# Eastron SDM630 input registers, 0-based Modbus PDU addresses.
REGISTERS = {
    "Leistung L1": 12,       # 30013
    "Leistung L2": 14,       # 30015
    "Leistung L3": 16,       # 30017
    "Gesamtleistung": 52,    # 30053
}

PARITY = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
}


def _get_serial_ports():
    """Return active serial ports, preferring stable /dev/serial/by-id paths.

    If a device is already represented by a by-id symlink, its /dev/ttyUSB*
    or /dev/ttyACM* alias is not added a second time.
    """
    ports = []
    represented_devices = set()

    for path in sorted(glob.glob("/dev/serial/by-id/*")):
        if os.path.exists(path):
            ports.append(path)
            represented_devices.add(os.path.realpath(path))

    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*"):
        for path in sorted(glob.glob(pattern)):
            if not os.path.exists(path):
                continue
            real_path = os.path.realpath(path)
            if real_path not in represented_devices:
                ports.append(path)
                represented_devices.add(real_path)

    # Keep the configuration dialog usable even when the adapter is unplugged
    # while CraftBeerPi starts.
    if not ports:
        ports.append("/dev/ttyUSB0")

    return ports


SERIAL_PORT_OPTIONS = _get_serial_ports()
DEFAULT_PORT = SERIAL_PORT_OPTIONS[0]

# One lock per physical serial port. This also serializes access if more than
# one Modbus slave is later used on the same RS485 bus.
_bus_locks: Dict[str, asyncio.Lock] = {}


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
        for name, address in REGISTERS.items():
            values[name] = float(instrument.read_float(
                registeraddress=address,
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
        entry.values = values
        entry.timestamp = time.monotonic()
        return values


@parameters([
    Property.Select(label="Port", options=SERIAL_PORT_OPTIONS,
                    description="Aktive serielle Schnittstelle; stabile /dev/serial/by-id-Pfade werden bevorzugt"),
    Property.Number(label="Slave", configurable=True, default_value=1,
                    description="Modbus-Adresse des SDM630 (Default: 1)"),
    # CBPi 4.7.x does not expose a default_value for Select properties in its
    # plugin metadata. Therefore the desired default is deliberately the first
    # option in each Select list.
    Property.Select(label="Baudrate", options=[9600, 2400, 4800, 19200, 38400],
                    description="Modbus-Baudrate (Default: 9600)"),
    Property.Select(label="Parity", options=["N", "E", "O"],
                    description="Paritaet (Default: N)"),
    Property.Select(label="Stopbits", options=[1, 2],
                    description="Stopbits (Default: 1)"),
    Property.Select(label="Messwert",
                    options=["Gesamtleistung", "Leistung L1", "Leistung L2", "Leistung L3"],
                    description="Anzuzeigender Leistungswert (Default: Gesamtleistung)"),
    Property.Select(label="Intervall", options=[2, 1, 5, 10, 30, 60],
                    description="Aktualisierungsintervall in Sekunden (Default: 2 s)"),
    Property.Number(label="Timeout", configurable=True, default_value=0.5,
                    description="Serieller Timeout in Sekunden (Default: 0.5 s)"),
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
        if self.measurement not in REGISTERS:
            self.measurement = "Gesamtleistung"

    async def run(self):
        cache_time = max(0.2, self.interval * 0.8)
        while self.running:
            try:
                values = await _get_values(
                    self.port, self.slave, self.baudrate, self.parity,
                    self.stopbits, self.timeout, cache_time
                )
                self.value = round(float(values[self.measurement]), 1)
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
