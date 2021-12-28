import asyncio
from enum import Enum
from io import BytesIO
from queue import Queue
from time import time
from typing import List, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from crc8 import crc8
from fastapi import FastAPI, File, UploadFile


Cmd = bytes
Cmds = List[Cmd]


CHR_PRINT = "0000ae01-0000-1000-8000-00805f9b34fb"
CHR_NOTIFY = "0000ae02-0000-1000-8000-00805f9b34fb"

CMD_FEED_PAPER = 0xA1

DELAY_CMDS = 0.01  # seconds
IDLE_TIMEOUT = 15  # seconds
PRINTER_NAMES = [
    "GT01",
    "GB01",
    "GB02",
    "GB03",
]


app = FastAPI()
print_queue = Queue()


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


def checksum(data: bytes) -> int:
    c = crc8()
    c.update(data)
    return c.digest()[0]


def build_cmd(cmd: int, data: List[int]) -> Cmd:
    return [
        0x51,
        0x78,
        cmd,
        0x00,
        len(data),
        0x00,
        *data,
        checksum(bytes(data)),
        0xFF,
    ]


class Printer:
    def __init__(self):
        self.device = None
        self.client = None

    def on_disconnect(self, _client):
        print("Disconnected")
        self.device = None
        self.client = None

    def on_notify(self, sender, data):
        print(f"Notify: {sender}: {data}")

    async def connect(self):
        if self.device:
            raise DeviceStateError("Device is already connected")
        self.device = await scan_for(PRINTER_NAMES)
        if not self.device:
            raise DeviceStateError("Device not found")
        self.client = BleakClient(self.device, disconnected_callback=self.on_disconnect)
        await self.client.connect()
        await self.client.start_notify(
            "0000ae02-0000-1000-8000-00805f9b34fb", self.on_notify
        )

    async def disconnect(self):
        if not self.device:
            raise DeviceStateError("Device is not connected")
        await self.client.disconnect()

    async def send(self, cmds: Cmds):
        if not self.device:
            raise DeviceStateError("Device is not connected")
        for cmd in cmds:
            print(cmd)
            await self.client.write_gatt_char(CHR_PRINT, cmd)
            await asyncio.sleep(DELAY_CMDS)

    async def feed(self, lines: int):
        cmds: Cmds = []
        while lines > 0:
            consumed = min(lines, 255)
            cmds.append(build_cmd(CMD_FEED_PAPER, [consumed]))
            lines -= consumed
        print(repr(cmds))
        await self.send(cmds)

    async def print(self, image: bytes):
        cmds: Cmds = []
        await self.send(cmds)


def wait_for_jobs():
    while True:
        job = print_queue.get(timeout=IDLE_TIMEOUT)
        if job:
            send_to_printer(job)
        else:
            if connected:
                disconnect()


@app.post("/print")
async def print_ep(image: UploadFile = File(...)):
    return {"filename": image.filename}


class DeviceStateError(Exception):
    pass


async def main():
    # printer = await scan_for(PRINTER_NAMES)
    # print(printer)
    # client = BleakClient(printer)
    # try:
    #     await client.connect()
    #     svcs = await client.get_services()
    #     for service in svcs:
    #         print(service)
    # finally:
    #     await client.disconnect()
    p = Printer()
    try:
        await p.connect()
        print("OK")
        await p.feed(1000)
    finally:
        await p.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
