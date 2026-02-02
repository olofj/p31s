#!/usr/bin/env python3
"""
Test the absolute printable limits of the P31S on 40x14mm labels.
Prints edge markers to find exact clipping boundaries.
"""

import asyncio
import sys

sys.path.insert(0, "src")
from PIL import Image, ImageDraw, ImageFont
from p31printer.connection import BLEConnection


def create_edge_test(width: int = 96, height: int = 320) -> Image.Image:
    """Create a test pattern showing exact pixel boundaries."""
    img = Image.new("1", (width, height), color=1)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 10)
    except:
        font = ImageFont.load_default()

    # Draw border at absolute edge (pixel 0)
    draw.rectangle([0, 0, width - 1, height - 1], outline=0, width=1)

    # Draw tick marks every 8 pixels on left edge with labels
    for y in range(0, height, 16):
        draw.line([(0, y), (10, y)], fill=0, width=1)
        if y % 32 == 0:
            draw.text((12, y - 4), str(y), font=font, fill=0)

    # Draw tick marks every 8 pixels on right edge
    for y in range(0, height, 16):
        draw.line([(width - 11, y), (width - 1, y)], fill=0, width=1)

    # Draw tick marks on top edge with labels
    for x in range(0, width, 16):
        draw.line([(x, 0), (x, 10)], fill=0, width=1)
        if x % 32 == 0 and x > 0:
            draw.text((x - 6, 12), str(x), font=font, fill=0)

    # Draw tick marks on bottom edge
    for x in range(0, width, 16):
        draw.line([(x, height - 11), (x, height - 1)], fill=0, width=1)

    # Center crosshair
    cx, cy = width // 2, height // 2
    draw.line([(cx - 20, cy), (cx + 20, cy)], fill=0, width=2)
    draw.line([(cx, cy - 20), (cx, cy + 20)], fill=0, width=2)

    # Label dimensions
    dim_text = f"{width}x{height}"
    bbox = draw.textbbox((0, 0), dim_text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, cy + 25), dim_text, font=font, fill=0)

    # Corner markers (solid squares to see if corners print)
    corner_size = 6
    # Top-left
    draw.rectangle([0, 0, corner_size, corner_size], fill=0)
    # Top-right
    draw.rectangle([width - corner_size - 1, 0, width - 1, corner_size], fill=0)
    # Bottom-left
    draw.rectangle([0, height - corner_size - 1, corner_size, height - 1], fill=0)
    # Bottom-right
    draw.rectangle([width - corner_size - 1, height - corner_size - 1, width - 1, height - 1], fill=0)

    return img


async def print_edge_test():
    """Print edge test at maximum dimensions."""

    # CONFIRMED MAX: 120x320 (15mm x 40mm)
    # - Width 120px works, 128px clips
    # - Height 320px fits one label, 336px spills to second
    bitmap_width = 120
    bitmap_height = 320

    print(f"Testing maximum dimensions: {bitmap_width}x{bitmap_height}")

    img = create_edge_test(bitmap_width, bitmap_height)
    img.save("edge_test_preview.png")
    print(f"Preview saved: edge_test_preview.png")

    # Convert to bitmap
    width_bytes = bitmap_width // 8
    bitmap_data = bytearray()

    for y in range(bitmap_height):
        row_byte = 0
        bit_pos = 7
        for x in range(bitmap_width):
            pixel = img.getpixel((x, y))
            if pixel != 0:
                row_byte |= (1 << bit_pos)
            bit_pos -= 1
            if bit_pos < 0:
                bitmap_data.append(row_byte)
                row_byte = 0
                bit_pos = 7

    # Dither solid black corners
    for i in range(len(bitmap_data)):
        if bitmap_data[i] == 0x00 and i % 4 == 0:
            bitmap_data[i] = 0x08

    print(f"Bitmap: {width_bytes} bytes/row x {bitmap_height} rows = {len(bitmap_data)} bytes")

    # Scan for printer
    print("\nScanning for printer...")
    printers = await BLEConnection.scan(timeout=5.0)
    if not printers:
        print("No printers found!")
        return False

    address = printers[0].address
    print(f"Found: {printers[0]}")

    conn = BLEConnection()
    if not await conn.connect(address):
        print("Failed to connect!")
        return False

    print("Connected!")

    try:
        # No offset - start at absolute 0,0
        x_offset = 0
        y_offset = 0

        commands = []
        commands.append(b"SIZE 14 mm,40 mm\r\n")
        commands.append(b"GAP 2 mm,0 mm\r\n")
        commands.append(b"DIRECTION 0,0\r\n")
        commands.append(b"DENSITY 12\r\n")
        commands.append(b"CLS\r\n")
        commands.append(f"BITMAP {x_offset},{y_offset},{width_bytes},{bitmap_height},1,".encode())
        commands.append(bytes(bitmap_data))
        commands.append(b"\r\n")
        commands.append(b"PRINT 1\r\n")

        job_data = b"".join(commands)
        print(f"Total job size: {len(job_data)} bytes")

        mtu = await conn.get_mtu()
        success = await conn.write_chunked(job_data, chunk_size=mtu)

        if success:
            print("Print job sent!")
        else:
            print("Print job failed!")

        return success

    finally:
        await conn.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    asyncio.run(print_edge_test())
