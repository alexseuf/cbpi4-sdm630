# -*- coding: utf-8 -*-
import asyncio
import logging
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

_bus_locks: Dict[Tuple[str, int], asyncio.Lock] = {}

@dataclass
class _CacheEntry:
    timestamp: float = 0.0
    values: Dict[str, float] = field(default_factory=dict)

_cache: Dict[Tuple[str, int, int, str, int], _CacheEntry] = {}


def _read_all_sync(port: str, slave: int, baudrate: int, parity: str,
                   stopbits: int, timeout: float):
    instrument = minimalmodbus.Instrument(port, slave, mode=minimalmodbus.MODE_RTU)
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

    try:
        instrument.serial.close()
    except Exception:
        pass
    return values


async def _get_values(port, slave, baudrate, parity, stopbits, timeout, cache_time):
    key = (port, slave, baudrate, parity, stopbits)
    bus_key = (port, slave)
    lock = _bus_locks.setdefault(bus_key, asyncio.Lock())
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
    Property.Text(label="Port", configurable=True,
                  default_value="/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A99RF4P0-if00-port0",
                  description="Serieller Port des USB/RS485-Wandlers"),
    Property.Number(label="Slave", configurable=True, default_value=1,
                    description="Modbus-Adresse des SDM630"),
    Property.Select(label="Baudrate", options=[2400, 4800, 9600, 19200, 38400],
                    description="Modbus-Baudrate"),
    Property.Select(label="Parity", options=["N", "E", "O"],
                    description="Paritaet"),
    Property.Select(label="Stopbits", options=[1, 2], description="Stopbits"),
    Property.Select(label="Messwert",
                    options=["Leistung L1", "Leistung L2", "Leistung L3", "Gesamtleistung"],
                    description="Anzuzeigender Leistungswert"),
    Property.Select(label="Intervall", options=[1, 2, 5, 10, 30, 60],
                    description="Aktualisierungsintervall in Sekunden"),
    Property.Number(label="Timeout", configurable=True, default_value=0.5,
                    description="Serieller Timeout in Sekunden"),
])
class SDM630PowerSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(SDM630PowerSensor, self).__init__(cbpi, id, props)
        self.value = 0.0
        self.port = str(self.props.get("Port", "/dev/ttyUSB0"))
        self.slave = int(float(self.props.get("Slave", 1)))
        self.baudrate = int(self.props.get("Baudrate", 9600))
        self.parity = str(self.props.get("Parity", "N"))
        self.stopbits = int(self.props.get("Stopbits", 1))
        self.measurement = str(self.props.get("Messwert", "Gesamtleistung"))
        self.interval = float(self.props.get("Intervall", 2))
        self.timeout = float(self.props.get("Timeout", 0.5))
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
