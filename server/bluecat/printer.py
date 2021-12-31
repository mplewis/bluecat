import asyncio
from contextlib import asynccontextmanager
from time import time
from typing import List, Optional

from bleak import BleakClient, BleakScanner, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


DISCOVERY_TIMEOUT = 15  # seconds to scan for a printer
IDLE_TIMEOUT = 15  # seconds to wait for a print job before disconnecting
CHR_PRINT = "0000AE01-0000-1000-8000-00805F9B34FB"
CHR_NOTIFY = "0000AE02-0000-1000-8000-00805F9B34FB"
BYTES_PER_SEND = 60  # max number of bytes to send in each WriteWithoutResponse
CONNECT_ATTEMPTS = 5  # number of times to try and connect to a printer before aborting


async def scan_for(names: List[str]) -> Optional[BLEDevice]:
    """Scan for a device with one of the given names."""
    device: BLEDevice = None

    def detection_callback(cand: BLEDevice, _: AdvertisementData):
        nonlocal device
        if device:
            return
        if cand.name in names:
            device = cand

    scanner = BleakScanner()
    scanner.register_detection_callback(detection_callback)
    start = time()
    await scanner.start()
    while time() - start < 5.0:
        if device:
            break
        await asyncio.sleep(0.1)
    await scanner.stop()
    return device


async def connect_to(device: BLEDevice) -> BleakClient:
    """Connect to a device."""
    client = BleakClient(device)
    attempt = 0
    while attempt < CONNECT_ATTEMPTS:
        try:
            await client.connect()
            break
        except BleakError as e:
            print(f"Connection attempt {attempt + 1} of {CONNECT_ATTEMPTS} failed: {e}")
            attempt += 1
    if not client.is_connected:
        raise PrinterError("Failed to connect to printer")
    return client


@asynccontextmanager
async def connected_client(names: List[str]) -> BleakClient:
    """Scan for and connect to a device with one of the given names."""
    device: BLEDevice = await scan_for(names)
    if not device:
        raise PrinterError("No printer found")
    client = await connect_to(device)
    try:
        yield client
    finally:
        await client.disconnect()


async def send_packets(client: BleakClient, cmds: bytes):
    """Send a sequence of bytes to the printer.

    This chops the sequence into chunks of BYTES_PER_SEND bytes.
    """
    pos = 0
    while pos < len(cmds):
        end = pos + BYTES_PER_SEND
        await client.write_gatt_char(CHR_PRINT, cmds[pos:end])
        pos += BYTES_PER_SEND


class PrinterError(Exception):
    """Something went wrong while communicating with the printer."""

    pass
