#!/usr/bin/env python3
import asyncio
import argparse

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from crc8 import crc8

import PIL.Image


def main():
    # General message format:
    # Magic number: 2 bytes 0x51, 0x78
    # Command: 1 byte
    # 0x00
    # Data length: 1 byte
    # 0x00
    # Data: Data Length bytes
    # CRC8 of Data: 1 byte
    # 0xFF
    def format_message(command, data):
        c = crc8()
        c.update(bytes(data))
        checksum = c.digest()[0]
        data = (
            [0x51, 0x78]
            + [command]
            + [0x00]
            + [len(data)]
            + [0x00]
            + data
            + [checksum]
            + [0xFF]
        )
        return data

    def printer_short(i):
        return [i & 0xFF, (i >> 8) & 0xFF]

    # Commands
    FeedPaper = 0xA1  # Data: Number of steps to go forward
    DrawBitmap = (
        0xA2  # Data: Line to draw. 0 bit -> don't draw pixel, 1 bit -> draw pixel
    )
    GetDevState = 0xA3  # Data: 0
    ControlLattice = 0xA6  # Data: Eleven bytes, all constants. One set used before printing, one after.
    OtherFeedPaper = (
        0xBD  # Data: one byte, set to a device-specific "Speed" value before printing
    )
    #                              and to 0x19 before feeding blank paper
    DrawingMode = 0xBE  # Data: 1 for Text, 0 for Images
    SetEnergy = 0xAF  # Data: 1 - 0xFFFF
    SetQuality = 0xA4  # Data: 0x31 - 0x35. APK always sets 0x33 for GB01

    PrintLattice = [0xAA, 0x55, 0x17, 0x38, 0x44, 0x5F, 0x5F, 0x5F, 0x44, 0x38, 0x2C]
    FinishLattice = [0xAA, 0x55, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x17]

    energy = {0: printer_short(8000), 1: printer_short(12000), 2: printer_short(17500)}
    contrast = 1

    PrinterWidth = 384

    ImgPrintSpeed = [0x23]
    BlankSpeed = [0x19]

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

    def request_status():
        return format_message(GetDevState, [0x00])

    def blank_paper(lines):
        # Feed extra paper for image to be visible
        blank_commands = format_message(OtherFeedPaper, BlankSpeed)
        count = lines
        while count:
            feed = min(count, 0xFF)
            blank_commands = blank_commands + format_message(
                FeedPaper, printer_short(feed)
            )
            count = count - feed
        return blank_commands

    def render_image(img):
        nonlocal header_lines
        nonlocal feed_lines

        cmdqueue = []
        # Set quality to standard
        cmdqueue += format_message(SetQuality, [0x33])
        # start and/or set up the lattice, whatever that is
        cmdqueue += format_message(ControlLattice, PrintLattice)
        # Set energy used
        cmdqueue += format_message(SetEnergy, energy[contrast])
        # Set mode to image mode
        cmdqueue += format_message(DrawingMode, [0])
        # not entirely sure what this does
        cmdqueue += format_message(OtherFeedPaper, ImgPrintSpeed)

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

            cmdqueue += format_message(DrawBitmap, bmp)

        # finish the lattice, whatever that means
        cmdqueue += format_message(ControlLattice, FinishLattice)

        return cmdqueue

    parser = argparse.ArgumentParser(
        description="Prints a given image to a GB01 thermal printer."
    )
    name_args = parser.add_mutually_exclusive_group(required=True)
    name_args.add_argument("filename", nargs="?", help="file name of an image to print")
    name_args.add_argument(
        "-e",
        "--eject",
        help="don't print an image, just feed some blank paper",
        action="store_true",
    )
    feed_args = parser.add_mutually_exclusive_group()
    feed_args.add_argument(
        "-E",
        "--no-eject",
        help="don't feed blank paper after printing the image",
        action="store_true",
    )
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
        "-m",
        "--medium",
        help="use moderate energy for moderate contrast",
        action="store_const",
        dest="contrast",
        const=1,
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
    if args.contrast:
        contrast = args.contrast
    throttle = args.throttle
    packet_length = args.packetsize
    feed_lines = args.feed
    if args.scale_feed:
        scale_feed = True

    print_data = request_status()
    if not args.eject:
        image = PIL.Image.open(args.filename)
        print_data = print_data + render_image(image)
    if not args.no_eject:
        print_data = print_data + blank_paper(feed_lines)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(connect_and_send(print_data))


if __name__ == "__main__":
    main()
