#!/usr/bin/env python3
import asyncio
import argparse
from typing import Union, Iterable

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from crc8 import crc8

import PIL.Image


def main():
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
        FeedRate = 0xBD
        DrawingMode = 0xBE
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

    PrintQuality = 0x33  # 0x31 to 0x35; app always uses 0x33
    PrintLattice = [0xAA, 0x55, 0x17, 0x38, 0x44, 0x5F, 0x5F, 0x5F, 0x44, 0x38, 0x2C]
    FinishLattice = [0xAA, 0x55, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x17]

    PrinterWidth = 384

    feed_lines = 112
    header_lines = 0
    scale_feed = False

    packet_length = 60
    throttle = 0.01

    PrinterCharacteristic = "0000AE01-0000-1000-8000-00805F9B34FB"
    device = None

    def detect_printer(detected, _advertisement_data):
        nonlocal device
        if detected.name == "GB03":
            device = detected

    async def connect_and_send(data):
        scanner = BleakScanner()
        scanner.register_detection_callback(detect_printer)
        await scanner.start()
        for x in range(50):
            await asyncio.sleep(0.1)
            if device:
                break
        await scanner.stop()

        if not device:
            raise BleakError("The printer was not found.")
        async with BleakClient(device) as client:
            while data:
                # Cut the command stream up into pieces small enough for the printer to handle
                await client.write_gatt_char(
                    PrinterCharacteristic, bytearray(data[:packet_length])
                )
                data = data[packet_length:]
                if throttle is not None:
                    await asyncio.sleep(throttle)

    def blank_paper(lines):
        # Feed extra paper for image to be visible
        blank_commands = format_message(Command.FeedRate, FeedRate.Blank)
        count = lines
        while count:
            feed = min(count, 0xFF)
            blank_commands = blank_commands + format_message(
                Command.FeedPaper, printer_short(feed)
            )
            count = count - feed
        return blank_commands

    def render_image(img):
        nonlocal header_lines
        nonlocal feed_lines

        cmdqueue = []
        cmdqueue += format_message(Command.SetQuality, PrintQuality)
        cmdqueue += format_message(Command.SetControlLattice, PrintLattice)
        cmdqueue += format_message(Command.SetEnergy, EnergyMode.High)
        cmdqueue += format_message(Command.DrawingMode, DrawingMode.Image)
        cmdqueue += format_message(Command.FeedRate, FeedRate.Print)

        if img.width > PrinterWidth:
            # image is wider than printer resolution; scale it down proportionately
            scale = PrinterWidth / img.width
            if scale_feed:
                header_lines = int(header_lines * scale)
                feed_lines = int(feed_lines * scale)
            img = img.resize((PrinterWidth, int(img.height * scale)))
        if img.width < (PrinterWidth // 2):
            # scale up to largest whole multiple
            scale = PrinterWidth // img.width
            if scale_feed:
                header_lines = int(header_lines * scale)
                feed_lines = int(feed_lines * scale)
            img = img.resize(
                (img.width * scale, img.height * scale), resample=PIL.Image.NEAREST
            )
        # convert image to black-and-white 1bpp color format
        img = img.convert("RGB")
        img = img.convert("1")
        if img.width < PrinterWidth:
            # image is narrower than printer resolution
            # pad it out with white pixels
            pad_amount = (PrinterWidth - img.width) // 2
            padded_image = PIL.Image.new("1", (PrinterWidth, img.height), 1)
            padded_image.paste(img, box=(pad_amount, 0))
            img = padded_image

        if header_lines:
            cmdqueue += blank_paper(header_lines)

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

        # finish the lattice, whatever that means
        cmdqueue += format_message(Command.SetControlLattice, FinishLattice)

        return cmdqueue

    parser = argparse.ArgumentParser(
        description="Prints a given image to a GB01 thermal printer."
    )
    name_args = parser.add_mutually_exclusive_group(required=True)
    name_args.add_argument("filename", nargs="?", help="file name of an image to print")
    feed_args = parser.add_mutually_exclusive_group()
    feed_args.add_argument(
        "-f",
        "--feed",
        type=int,
        default=feed_lines,
        metavar="LINES",
        help="amount of blank paper to feed (default: {})".format(feed_lines),
    )
    parser.add_argument(
        "--header",
        type=int,
        metavar="LINES",
        help="feed blank paper before printing the image",
    )
    parser.add_argument(
        "--scale-feed",
        help="adjust blank paper feed proportionately when resizing image",
        action="store_true",
    )
    contrast_args = parser.add_mutually_exclusive_group()
    contrast_args.add_argument(
        "-l",
        "--light",
        help="use less energy for light contrast",
        action="store_const",
        dest="contrast",
        const=0,
    )
    contrast_args.add_argument(
        "-d",
        "--dark",
        help="use more energy for high contrast",
        action="store_const",
        dest="contrast",
        const=2,
    )
    parser.add_argument(
        "-A",
        "--address",
        help="MAC address of printer in hex (rightmost digits, colons optional)",
    )
    parser.add_argument(
        "-D",
        "--debug",
        help="output notifications received from printer, in hex",
        action="store_true",
    )
    throttle_args = parser.add_mutually_exclusive_group()
    throttle_args.add_argument(
        "-t",
        "--throttle",
        type=float,
        default=throttle,
        metavar="SECONDS",
        help="delay between sending command queue packets (default: {})".format(
            throttle
        ),
    )
    throttle_args.add_argument(
        "-T",
        "--no-throttle",
        help="don't wait while sending data",
        action="store_const",
        dest="throttle",
        const=None,
    )
    parser.add_argument(
        "-p",
        "--packetsize",
        type=int,
        default=packet_length,
        metavar="BYTES",
        help="length of a command queue packet (default: {})".format(packet_length),
    )
    args = parser.parse_args()
    throttle = args.throttle
    packet_length = args.packetsize
    feed_lines = args.feed
    if args.scale_feed:
        scale_feed = True

    image = PIL.Image.open(args.filename)

    print_data = []
    print_data = print_data + render_image(image)
    print_data = print_data + blank_paper(feed_lines)

    asyncio.run(connect_and_send(print_data))


if __name__ == "__main__":
    main()
