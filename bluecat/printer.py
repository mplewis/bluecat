import asyncio
from queue import Queue
from time import time
from typing import List, Optional

from bleak import BleakClient, BleakScanner, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


DISCOVERY_TIMEOUT = 15  # seconds to scan for a printer
CHR_PRINT = "0000AE01-0000-1000-8000-00805F9B34FB"
CHR_NOTIFY = "0000AE02-0000-1000-8000-00805F9B34FB"
BYTES_PER_SEND = 60  # max number of bytes to send in each WriteWithoutResponse
CMD_DELAY = 0.01  # seconds between WriteWithoutResponse calls
CONNECT_ATTEMPTS = 5  # number of times to try and connect to a printer before aborting
PRINTER_NAMES = [  # cat printers have one of these names as their BLE-advertised name.
    "GT01",
    "GB01",
    "GB02",
    "GB03",
]


async def scan_for(names: List[str]) -> Optional[BLEDevice]:
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


class Printer:
    def __init__(self):
        self.device: BLEDevice = None
        self.client: BleakClient = None

    def on_disconnect(self, _client):
        print("Disconnected")
        self.device = None
        self.client = None

    def on_notify(self, sender, data):
        print(f"Notify: {sender}: {data}")

    async def connect(self):
        if self.device:
            raise PrinterError("Printer is already connected")

        self.device = await scan_for(PRINTER_NAMES)
        if not self.device:
            raise PrinterError("Printer not found")

        self.client = BleakClient(self.device, disconnected_callback=self.on_disconnect)

        attempt = 0
        while attempt < CONNECT_ATTEMPTS:
            try:
                await self.client.connect()
                break
            except BleakError as e:
                print(f"Connection attempt {attempt} of {CONNECT_ATTEMPTS} failed: {e}")
                attempt += 1
        if not self.client.is_connected:
            raise PrinterError("Failed to connect to printer")

        await self.client.start_notify(CHR_NOTIFY, self.on_notify)

    async def disconnect(self):
        if not self.device:
            raise PrinterError("Printer is not connected")
        await self.client.disconnect()

    async def send(self, cmds: bytes):
        if not self.device:
            raise PrinterError("Printer is not connected")
        pos = 0
        while pos < len(cmds):
            end = pos + BYTES_PER_SEND
            await self.client.write_gatt_char(CHR_PRINT, cmds[pos:end])
            pos += BYTES_PER_SEND


def wait_for_jobs():
    while True:
        job = print_queue.get(timeout=IDLE_TIMEOUT)
        if job:
            send_to_printer(job)
        else:
            if connected:
                disconnect()


class PrinterError(Exception):
    pass
