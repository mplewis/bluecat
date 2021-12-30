import asyncio
import os
import tempfile
from multiprocessing import Process
from queue import Queue, Empty
from time import time
from typing import List

from fastapi import FastAPI, File

from bluecat.printer import connected_client, send_packets
from bluecat.protocol import (
    cmd_print_and_feed,
    PrintAndFeedArgs,
    EnergyMode,
)

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

SECS_PER_LINE = 0.0372  # seconds taken per line of image printed
PRINTER_NAMES = [
    "GT01",
    "GB01",
    "GB02",
    "GB03",
]

print_args = PrintAndFeedArgs(
    filename=None,  # replaced on print
    padding=40,
    energy_mode=EnergyMode.High,
)


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

app = FastAPI()
file_print_queue = Queue()


async def worker():
    while True:
        try:
            filename = file_print_queue.get(block=False)
            print(f"Printing {filename}")
            print_args.filename = filename
            await print_image(print_args)
            os.unlink(filename)
        except Empty:
            await asyncio.sleep(0.1)
        except Exception as e:
            print(e)


asyncio.create_task(worker())


@app.post("/print")
def print_ep(image: bytes = File(...)):
    target = tempfile.NamedTemporaryFile(delete=False)
    with open(target.name, "wb") as f:
        f.write(image)
    file_print_queue.put(target.name)
    print(target.name)
    return "OK"


async def print_image(args: PrintAndFeedArgs):
    c = cmd_print_and_feed(args)
    async with connected_client(PRINTER_NAMES) as client:
        start = time()
        await send_packets(client, c.data)
    while time() - start < c.print_time:
        await asyncio.sleep(0.1)


asyncio.create_task(worker())
