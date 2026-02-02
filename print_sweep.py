#!/usr/bin/env python3
"""
Print a sweep of test labels with different margin settings.
Each label shows its own parameters for easy comparison.
"""

import asyncio
import sys

sys.path.insert(0, "src")
from PIL import Image, ImageDraw, ImageFont
from p31printer.connection import BLEConnection


def create_test_label(pad_x: int, y_off: int, width: int = 96, height: int = 312) -> Image.Image:
    """Create a test label showing its own settings."""
    img = Image.new("1", (width, height), color=1)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 10)
    except:
        font = ImageFont.load_default()
        font_small = font

    # Border rectangle (within content area defined by pad_x)
    draw.rectangle([pad_x, 2, width - pad_x - 1, height - 3], outline=0, width=2)

    # Draw corner markers to show exact printable area
    # Top-left corner
    draw.line([(pad_x, 10), (pad_x + 15, 10)], fill=0, width=1)
    draw.line([(pad_x + 10, 2), (pad_x + 10, 17)], fill=0, width=1)

    # Bottom-right corner
    draw.line([(width - pad_x - 16, height - 11), (width - pad_x - 1, height - 11)], fill=0, width=1)
    draw.line([(width - pad_x - 11, height - 18), (width - pad_x - 11, height - 3)], fill=0, width=1)

    # Settings text - show pad_x and y_off
    settings_text = f"px={pad_x}"
    bbox = draw.textbbox((0, 0), settings_text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, 30), settings_text, font=font, fill=0)

    settings_text2 = f"yo={y_off}"
    bbox = draw.textbbox((0, 0), settings_text2, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, 50), settings_text2, font=font, fill=0)

    # Test number (will be set externally)
    # Draw a center line to check horizontal centering
    center_x = width // 2
    draw.line([(center_x, 80), (center_x, 120)], fill=0, width=2)

    # Label "CENTER" below the line
    center_text = "CTR"
    bbox = draw.textbbox((0, 0), center_text, font=font_small)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, 125), center_text, font=font_small, fill=0)

    # Draw measurement bars at different positions to check alignment
    # These are at fixed pixel positions to help identify optimal pad_x
    for i, px in enumerate([4, 8, 12, 16]):
        y_pos = 160 + i * 30
        # Left marker at px from left edge
        draw.rectangle([px, y_pos, px + 4, y_pos + 20], fill=0)
        # Right marker at px from right edge
        draw.rectangle([width - px - 5, y_pos, width - px - 1, y_pos + 20], fill=0)
        # Label
        draw.text((width // 2 - 8, y_pos + 3), f"{px}", font=font_small, fill=0)

    # Checkerboard at bottom to verify print quality
    for y in range(height - 25, height - 8):
        for x in range(pad_x + 2, width - pad_x - 2):
            if (x + y) % 4 < 2:
                draw.point((x, y), fill=0)

    return img


async def print_sweep():
    """Print multiple test labels with different settings."""

    # Settings to test - vary pad_x and y_offset
    # pad_x: internal padding within the 96px bitmap
    # y_offset: vertical offset in TSPL command
    test_configs = [
        {"pad_x": 4, "y_off": 0},
        {"pad_x": 8, "y_off": 0},
        {"pad_x": 12, "y_off": 0},
        {"pad_x": 8, "y_off": 2},
        {"pad_x": 8, "y_off": 4},
        {"pad_x": 6, "y_off": 2},
    ]

    print(f"Will print {len(test_configs)} test labels")
    print("Settings to test:")
    for i, cfg in enumerate(test_configs):
        print(f"  #{i+1}: pad_x={cfg['pad_x']}, y_off={cfg['y_off']}")

    # Scan for printer
    print("\nScanning for printer...")
    printers = await BLEConnection.scan(timeout=5.0)
    if not printers:
        print("No printers found!")
        return False

    address = printers[0].address
    print(f"Found: {printers[0]}\n")

    for i, cfg in enumerate(test_configs):
        pad_x = cfg["pad_x"]
        y_off = cfg["y_off"]

        print(f"Printing #{i+1}: pad_x={pad_x}, y_off={y_off}...")

        # Create image
        img = create_test_label(pad_x, y_off)

        # Save preview
        img.save(f"sweep_preview_{i+1}.png")

        # Convert to bitmap
        bitmap_width = 96
        bitmap_height = 312
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

        # Dither solid black
        for j in range(len(bitmap_data)):
            if bitmap_data[j] == 0x00 and j % 4 == 0:
                bitmap_data[j] = 0x08

        # Build TSPL commands
        commands = []
        commands.append(b"SIZE 10 mm,40 mm\r\n")
        commands.append(b"GAP 2 mm,0 mm\r\n")
        commands.append(b"DIRECTION 0,0\r\n")
        commands.append(b"DENSITY 12\r\n")
        commands.append(b"CLS\r\n")
        commands.append(f"BITMAP 0,{y_off},{width_bytes},{bitmap_height},1,".encode())
        commands.append(bytes(bitmap_data))
        commands.append(b"\r\n")
        commands.append(b"PRINT 1\r\n")

        job_data = b"".join(commands)

        # Connect for this job
        conn = BLEConnection()
        if not await conn.connect(address):
            print(f"  #{i+1} FAILED to connect")
            continue

        try:
            mtu = await conn.get_mtu()
            success = await conn.write_chunked(job_data, chunk_size=mtu)

            if success:
                print(f"  #{i+1} sent OK")
            else:
                print(f"  #{i+1} FAILED")
        finally:
            await conn.disconnect()

        # Wait for print to complete before next job
        print(f"  Waiting for print to finish...")
        await asyncio.sleep(5.0)

    print("\nAll test labels printed!")
    return True


if __name__ == "__main__":
    asyncio.run(print_sweep())
