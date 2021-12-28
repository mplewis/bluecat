import asyncio
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
CMD_PRINT_BITS = 0xA2
CMD_PRINT_RLE = 0xBF
CMD_SET_LATTICE = 0xA6
CMD_SET_DRAW_MODE = 0xBE
CMD_SET_QUALITY = 0xA4
CMD_SET_ENERGY = 0xAF

DATA_LATTICE_START = [0xAA, 0x55, 0x17, 0x38, 0x44, 0x5F, 0x5F, 0x5F, 0x44, 0x38, 0x2C]
DATA_LATTICE_END = [0xAA, 0x55, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x17]

BLACK = 1
WHITE = 0

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


def run_byte(color: int, count: int) -> Cmd:
    if count > 0x7F:
        raise ValueError("count must be <= 0x7f")
    msb = 0x00
    if color == BLACK:
        msb = 0x80
    return count | msb


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
    cmds = []
    cmds.append(build_cmd(CMD_SET_DRAW_MODE, [0x00]))
    cmds.append(build_cmd(CMD_SET_ENERGY, [0x2E]))
    cmds.append(build_cmd(CMD_SET_QUALITY, [0x33]))
    cmds.append(build_cmd(CMD_SET_LATTICE, DATA_LATTICE_START))

    cols = 10
    rows = 4
    sqSize = 50
    checkersRowA = []
    checkersRowB = []
    for xsq in range(cols):
        for _ in range(sqSize):
            aColor = xsq % 2
            bColor = 1 - aColor
            checkersRowA.append(run_byte(aColor, sqSize))
            checkersRowB.append(run_byte(bColor, sqSize))

    for y in range(rows * sqSize):
        row = checkersRowA
        if int(y / sqSize) % 2 == 0:
            row = checkersRowB
        cmds.append(build_cmd(CMD_PRINT_RLE, row))

    cmds.append(build_cmd(CMD_SET_LATTICE, DATA_LATTICE_END))

    for cmd in cmds:
        print(" ".join(f"0x{x:02x}" for x in cmd))

    p = Printer()
    try:
        await p.connect()
        print("OK")
        await p.send(cmds)
    finally:
        await p.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
