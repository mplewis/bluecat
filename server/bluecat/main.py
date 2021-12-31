import asyncio
import os
import tempfile
import traceback
from queue import Queue, Empty
from time import time

from fastapi import FastAPI, File

from bluecat.printer import connected_client, send_packets
from bluecat.protocol import (
    cmd_print_and_feed,
    PrintAndFeedArgs,
    EnergyMode,
)

PRINTER_NAMES = [
    "GT01",
    "GB01",
    "GB02",
    "GB03",
]


# Default arguments for a print job.
print_args = PrintAndFeedArgs(
    filename=None,  # replaced on print
    padding=120,
    energy_mode=EnergyMode.High,
)


app = FastAPI()
file_print_queue = Queue()  # Contains filenames to print.


async def print_image(args: PrintAndFeedArgs):
    """Print a single image."""
    c = cmd_print_and_feed(args)
    async with connected_client(PRINTER_NAMES) as client:
        start = time()
        await send_packets(client, c.data)
    while time() - start < c.print_time:
        await asyncio.sleep(0.1)


async def worker():
    """Manage the print queue."""
    while True:
        try:
            filename = file_print_queue.get(block=False)
            print(f"Printing {filename}")
            print_args.filename = filename
            await print_image(print_args)
            os.unlink(filename)
        except Empty:
            await asyncio.sleep(0.1)
        except Exception:
            traceback.print_exc()


@app.post("/print")
def print_ep(image: bytes = File(...)):
    """Handle print requests."""
    target = tempfile.NamedTemporaryFile(delete=False)
    with open(target.name, "wb") as f:
        f.write(image)
    file_print_queue.put(target.name)
    print(target.name)
    return "OK"


asyncio.create_task(worker())
