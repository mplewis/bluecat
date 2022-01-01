import asyncio
import os
import tempfile
import traceback
from dataclasses import dataclass
from queue import Queue, Empty
from time import time
from typing import Union

from fastapi import FastAPI, File

from bluecat.printer import connected_client, send_packets
from bluecat.protocol import (
    cmd_feed_paper,
    cmd_print_and_feed,
    PrintAndFeedArgs,
    EnergyMode,
)


# Default arguments for a print job.
print_args = PrintAndFeedArgs(
    filename=None,  # replaced on print
    padding=40,
    energy_mode=EnergyMode.High,
)

FEED_AMOUNT = 80  # Number of lines to feed when asked to feed paper without printing.

# Advertised names for the cat printer.
PRINTER_NAMES = [
    "GT01",
    "GB01",
    "GB02",
    "GB03",
]


@dataclass
class PrintJob:
    """A file to print."""

    filename: str


@dataclass
class FeedJob:
    """Indicates that lines of paper should be fed."""

    pass


Job = Union[PrintJob, FeedJob]

app = FastAPI()
job_queue: Queue[Job] = Queue()  # Contains jobs to print.


async def send_to_printer(job: Job):
    """Print a single image."""
    if isinstance(job, PrintJob):
        print_args.filename = job.filename
        c = cmd_print_and_feed(print_args)
        async with connected_client(PRINTER_NAMES) as client:
            print("Connected")
            start = time()
            await send_packets(client, c.data)
            print("Waiting for print to complete...")
        while time() - start < c.print_time:
            await asyncio.sleep(0.1)
        os.unlink(job.filename)
        print("Print complete.")

    elif isinstance(job, FeedJob):
        c = cmd_feed_paper(FEED_AMOUNT)
        async with connected_client(PRINTER_NAMES) as client:
            print("Connected")
            start = time()
            await send_packets(client, c.data)
            print("Waiting for feed to complete...")
        while time() - start < c.print_time:
            await asyncio.sleep(0.1)
        print("Feed complete.")

    else:
        print(f"Unsupported job type {job.__class__.__name__}, discarding")


async def worker():
    """Manage the print queue."""
    while True:
        job = None
        try:
            job = job_queue.get(block=False)
            await send_to_printer(job)
        except Empty:
            await asyncio.sleep(0.1)
        except Exception:
            traceback.print_exc()
            if job:
                job_queue.put(job)
            await asyncio.sleep(5)


@app.post("/print")
def print_ep(image: bytes = File(...)):
    """Handle print requests."""
    target = tempfile.NamedTemporaryFile(delete=False)
    with open(target.name, "wb") as f:
        f.write(image)
    job_queue.put(PrintJob(target.name))
    return "OK"


@app.post("/feed")
def feed_ep():
    """Feed some paper."""
    job_queue.put(FeedJob())
    return "OK"


asyncio.create_task(worker())
