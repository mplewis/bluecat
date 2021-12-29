#!/usr/bin/env python3
import asyncio
from dataclasses import dataclass
from time import time
from typing import Union, Iterable

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from crc8 import crc8

import PIL.Image


DISCOVERY_TIMEOUT = 15  # seconds to scan for a printer
PRINTER_WIDTH = 384  # pixels
CHR_PRINT = "0000AE01-0000-1000-8000-00805F9B34FB"
CMD_DELAY = 0.01  # seconds between characteristic WriteWithoutResponse calls
CMD_MAX_LEN = 60  # bytes per characteristic WriteWithoutResponse call
PRINTER_NAMES = [
    "GT01",
    "GB01",
    "GB02",
    "GB03",
]


@dataclass
class Args:
    filename: str


def main(args: Args):
    def format_message(command, data: Union[int, Iterable[int]]) -> bytes:
        if not isinstance(data, Iterable):
            data = [data]
        c = crc8()
        c.update(bytes(data))
        checksum = c.digest()[0]
        return (
            [0x51, 0x78]
            + [command]
            + [0x00]
            + [len(data)]
            + [0x00]
            + data
            + [checksum]
            + [0xFF]
        )

    def printer_short(i):
        return [i & 0xFF, (i >> 8) & 0xFF]

    class Command:
        FeedPaper = 0xA1  # steps to advance paper
        DrawBitmap = 0xA2  # 1 bit = black dot
        SetFeedRate = 0xBD
        SetDrawingMode = 0xBE
        SetEnergy = 0xAF  # 0x0001 to 0xFFFF
        SetQuality = 0xA4
        SetControlLattice = 0xA6  # 11-byte magic data

    class FeedRate:
        Print = 0x23
        Blank = 0x19

    class DrawingMode:
        Image = 0x00
        Text = 0x01

    class EnergyMode:
        Low = printer_short(8000)
        Medium = printer_short(12000)
        High = printer_short(17500)

    class PrintQuality:
        A = 0x31
        B = 0x32
        C = 0x33  # Android app default
        D = 0x34
        E = 0x35

    PrintLattice = [0xAA, 0x55, 0x17, 0x38, 0x44, 0x5F, 0x5F, 0x5F, 0x44, 0x38, 0x2C]
    FinishLattice = [0xAA, 0x55, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x17]

    feed_lines = 112

    device = None

    def detect_printer(detected, _advertisement_data):
        nonlocal device
        if detected.name in PRINTER_NAMES:
            device = detected

    async def connect_and_send(data):
        scanner = BleakScanner()
        scanner.register_detection_callback(detect_printer)

        await scanner.start()
        start = time()
        while time() - start < DISCOVERY_TIMEOUT:
            await asyncio.sleep(0.1)
            if device:
                break
        await scanner.stop()
        if not device:
            raise BleakError("device not found")

        async with BleakClient(device) as client:
            while data:
                # Cut the command stream up into pieces small enough for the printer to handle
                await client.write_gatt_char(CHR_PRINT, bytearray(data[:CMD_MAX_LEN]))
                data = data[CMD_MAX_LEN:]
                await asyncio.sleep(CMD_DELAY)

    def blank_paper(lines):
        blank_commands = format_message(Command.SetFeedRate, FeedRate.Blank)
        while lines:
            feed = min(lines, 0xFF)
            blank_commands += format_message(Command.FeedPaper, printer_short(feed))
            lines = lines - feed
        return blank_commands

    def render_image(img):
        nonlocal feed_lines

        cmdqueue = []
        cmdqueue += format_message(Command.SetQuality, PrintQuality.C)
        cmdqueue += format_message(Command.SetControlLattice, PrintLattice)
        cmdqueue += format_message(Command.SetEnergy, EnergyMode.High)
        cmdqueue += format_message(Command.SetDrawingMode, DrawingMode.Image)
        cmdqueue += format_message(Command.SetFeedRate, FeedRate.Print)

        if img.width > PRINTER_WIDTH:
            # image is wider than printer resolution; scale it down proportionately
            scale = PRINTER_WIDTH / img.width
            img = img.resize((PRINTER_WIDTH, int(img.height * scale)))
        if img.width < (PRINTER_WIDTH // 2):
            # scale up to largest whole multiple
            scale = PRINTER_WIDTH // img.width
            img = img.resize(
                (img.width * scale, img.height * scale), resample=PIL.Image.NEAREST
            )
        img = img.convert("RGB").convert("1")
        if img.width < PRINTER_WIDTH:
            pad_amount = (PRINTER_WIDTH - img.width) // 2
            padded_image = PIL.Image.new("1", (PRINTER_WIDTH, img.height), 1)
            padded_image.paste(img, box=(pad_amount, 0))
            img = padded_image

        for y in range(0, img.height):
            bmp = []
            bit = 0

            # pack image data into 8 pixels per byte
            for x in range(0, img.width):
                if bit % 8 == 0:
                    bmp += [0x00]
                bmp[int(bit / 8)] >>= 1
                if not img.getpixel((x, y)):
                    bmp[int(bit / 8)] |= 0x80
                else:
                    bmp[int(bit / 8)] |= 0
                bit += 1

            cmdqueue += format_message(Command.DrawBitmap, bmp)

        cmdqueue += format_message(Command.SetControlLattice, FinishLattice)
        return cmdqueue

    image = PIL.Image.open(args.filename)

    print_data = []
    print_data = print_data + render_image(image)
    print_data = print_data + blank_paper(feed_lines)

    asyncio.run(connect_and_send(print_data))


if __name__ == "__main__":
    args = Args(
        filename="tmp/redrocks.pbm",
    )
    main(args)
