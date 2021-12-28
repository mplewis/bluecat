import asyncio
from queue import Queue
from time import time
from typing import List, Optional

from bleak import BleakClient, BleakScanner
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
        self.client = None

    def on_disconnect(self, _client):
        print('Disconnected')
        self.device = None
        self.client = None

    def on_notify(self, sender, data):
        print(f'Notify: {sender}: {data}')

    async def connect(self):
        if self.device:
            raise DeviceStateError('Device is already connected')
        self.device = await scan_for(PRINTER_NAMES)
        if not self.device:
            raise DeviceStateError('Device not found')
        self.client = BleakClient(self.device, disconnected_callback=self.on_disconnect)
        await self.client.connect()
        await self.client.start_notify('0000ae02-0000-1000-8000-00805f9b34fb', self.on_notify)

    async def disconnect(self):
        if not self.device:
            raise DeviceStateError('Device is not connected')
        await self.client.disconnect()

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
        print('OK')
    finally:
        await p.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
