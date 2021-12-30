import asyncio
from typing import List

from fastapi import FastAPI, File, UploadFile

from bluecat.printer import Printer
from bluecat.protocol import cmd_print_and_feed, PrintAndFeedArgs, EnergyMode

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


@app.post("/print")
async def print_ep(image: UploadFile = File(...)):
    return {"filename": image.filename}


async def main():
    filenames = [
        "tmp/redrocks.pbm",
        # "tmp/daftpunk.jpg",
        # "tmp/redrocks.pbm",
    ]
    cmds = []
    for fn in filenames:
        args = PrintAndFeedArgs(
            filename=fn,
            padding=40,
            energy_mode=EnergyMode.High,
        )
        cmds.extend(cmd_print_and_feed(args))

    p = Printer()
    try:
        await p.connect()
        await p.send(cmds)
    finally:
        await p.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
