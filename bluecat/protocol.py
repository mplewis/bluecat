#!/usr/bin/env python3
import asyncio
from dataclasses import dataclass
from time import time
from typing import Union, Iterable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from crc8 import crc8

import PIL.Image


DISCOVERY_TIMEOUT = 15  # seconds to scan for a printer
PRINTER_WIDTH = 384  # pixels
CHR_PRINT = "0000AE01-0000-1000-8000-00805F9B34FB"
CMD_DELAY = 0.01  # seconds between characteristic WriteWithoutResponse calls
CMD_MAX_LEN = 60  # bytes per characteristic WriteWithoutResponse call
PRINTER_NAMES = [  # Cat printers have one of these names as their BLE-advertised name.
    "GT01",
    "GB01",
    "GB02",
    "GB03",
]


def uint16_le(i: int) -> bytes:
    """Convert a number to little-endian uint16 bytes."""
    return [i & 0xFF, (i >> 8) & 0xFF]


class Command:
    """Commands for controlling the printer."""

    FeedPaper = 0xA1  # steps to advance paper
    DrawBitmap = 0xA2  # 1 bit = black dot
    SetFeedRate = 0xBD
    SetDrawingMode = 0xBE
    SetEnergy = 0xAF  # 0x0001 to 0xFFFF
    SetQuality = 0xA4
    SetControlLattice = 0xA6  # 11-byte magic data


class FeedRate:
    """Fixed feed rates for printer functions."""

    Print = 0x23
    Blank = 0x19


class DrawingMode:
    """The drawing mode for the printer's graphics."""

    Image = 0x00
    Text = 0x01


class EnergyMode:
    """The energy mode for the printer, from 0x0000 to 0xFFFF.

    Higher energy modes use more power and produce darker pixels.
    """

    Low = 8000
    Medium = 12000
    High = 17500


class PrintQuality:
    """The print quality.

    The Android app always uses 0x33. I'm unclear how this parameter affects the image.
    """

    A = 0x31
    B = 0x32
    C = 0x33  # Android app default
    D = 0x34
    E = 0x35


class Lattice:
    """The lattice is used to control some mode of the printer.

    I don't understand how this works.
    """

    Start = [0xAA, 0x55, 0x17, 0x38, 0x44, 0x5F, 0x5F, 0x5F, 0x44, 0x38, 0x2C]
    Finish = [0xAA, 0x55, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x17]


@dataclass
class PrintAndFeedArgs:
    """The arguments for a print job."""

    filename: str
    padding: int = 0
    drawing_mode: int = DrawingMode.Image
    energy_mode: int = EnergyMode.Medium
    print_quality: int = PrintQuality.C


def format_message(command: int, data: Union[int, Iterable[int]]) -> bytes:
    """Build a message for the printer."""
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


def cmd_print_image(
    img: PIL.Image,
    drawing_mode: int,
    energy_mode: int,
    print_quality: int,
) -> bytes:
    """Build a command that prints an image."""
    cmds = []
    cmds += format_message(Command.SetDrawingMode, drawing_mode)
    cmds += format_message(Command.SetEnergy, uint16_le(energy_mode))
    cmds += format_message(Command.SetQuality, print_quality)
    cmds += format_message(Command.SetFeedRate, FeedRate.Print)
    cmds += format_message(Command.SetControlLattice, Lattice.Start)

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

        cmds += format_message(Command.DrawBitmap, bmp)

    cmds += format_message(Command.SetControlLattice, Lattice.Finish)
    return cmds


def cmd_feed_paper(lines) -> bytes:
    """Build a command that feeds paper."""
    blank_commands = format_message(Command.SetFeedRate, FeedRate.Blank)
    while lines:
        feed = min(lines, 0xFF)
        blank_commands += format_message(Command.FeedPaper, uint16_le(feed))
        lines = lines - feed
    return blank_commands


def cmd_print_and_feed(args: PrintAndFeedArgs) -> bytes:
    """Build a command that prints an image, then feeds paper."""
    image = PIL.Image.open(args.filename)
    return [
        *cmd_print_image(
            image,
            args.drawing_mode,
            args.energy_mode,
            args.print_quality,
        ),
        *cmd_feed_paper(args.padding),
    ]
