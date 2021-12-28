import asyncio
from queue import Queue
from time import time
from typing import List, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from fastapi import FastAPI, File, UploadFile


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



class Printer:
    def __init__(self):
        self.device = None

    def connect(self):
        if self.device:
            raise DeviceStateError('Device is already connected')
        self.device = scan_for(PRINTER_NAMES)

    def disconnect(self):
        if not self.device:
            raise DeviceStateError('Device is not connected')
        self.device.disconnect()
        self.device = None

    def send(self, cmds):
        if not self.device:
            raise DeviceStateError('Device is not connected')
        # TODO
        self.device.send(cmds)

    def feed(self, lines: int):
        cmds = build_commands_for('feed', lines)
        self.send(cmds)

    def print(self, image: bytes):
        cmds = build_commands_for(image)
        self.send(cmds)


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
    printer = await scan_for(PRINTER_NAMES)
    print(printer)

if __name__ == '__main__':
    asyncio.run(main())
