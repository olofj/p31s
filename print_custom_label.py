#!/opt/homebrew/opt/python@3.10/bin/python3.10
"""
Print a custom label with text and graphics on P31S printer.
Label: 40mm x 10mm (tall, narrow) at 203 DPI
"""

import asyncio
import sys

sys.path.insert(0, "src")
from PIL import Image, ImageDraw, ImageFont
from p31printer.connection import BLEConnection



def create_label_image(text: str = "HELLO", width: int = 96, height: int = 312) -> Image.Image:
    """Create a label image with text.

    Width is 96px (full print head). Asymmetric padding centers content on 10mm label.
    Settings verified via sweep testing.
    """
    img = Image.new("1", (width, height), color=1)  # 1 = white
    draw = ImageDraw.Draw(img)

    # Asymmetric padding to center content on physical label
    pad_left = 4
    pad_right = 12
    content_width = width - pad_left - pad_right  # 80px

    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except:
        font_large = ImageFont.load_default()
        font_small = font_large

    # Border rectangle (within content area)
    draw.rectangle([pad_left + 2, 2, width - pad_right - 3, height - 3], outline=0, width=2)

    # Arrow at top pointing "up" (feed direction)
    arrow_y = 20
    arrow_center = pad_left + content_width // 2
    draw.polygon([
        (arrow_center, arrow_y - 10),      # tip
        (arrow_center - 8, arrow_y + 5),   # left
        (arrow_center + 8, arrow_y + 5),   # right
    ], fill=0)
    draw.rectangle([arrow_center - 3, arrow_y + 5, arrow_center + 3, arrow_y + 20], fill=0)

    # Stack letters vertically
    text_y = 60
    center_x = pad_left + content_width // 2
    for i, char in enumerate(text):
        bbox = draw.textbbox((0, 0), char, font=font_large)
        char_width = bbox[2] - bbox[0]
        char_x = center_x - char_width // 2
        draw.text((char_x, text_y + i * 35), char, font=font_large, fill=0)

    # "P31S" label at bottom
    label_text = "P31S"
    bbox = draw.textbbox((0, 0), label_text, font=font_small)
    label_width = bbox[2] - bbox[0]
    draw.text((center_x - label_width // 2, height - 35), label_text, font=font_small, fill=0)

    # Checkerboard strip at very bottom (within content area)
    for y in range(height - 18, height - 4):
        for x in range(pad_left + 4, width - pad_right - 4):
            if (x + y) % 4 < 2:
                draw.point((x, y), fill=0)

    return img


async def scan_for_printer() -> str | None:
    """Scan for P31S printer and return its address."""
    print("Scanning for P31S printers...")
    printers = await BLEConnection.scan(timeout=5.0)

    if not printers:
        print("No printers found.")
        return None

    print(f"Found: {printers[0]}")
    return printers[0].address


async def print_label(text: str = "HELLO"):
    """Print a custom label."""
    print(f"Creating label with text: {text}")

    bitmap_width = 96  # Full 12mm print head width at 203 DPI
    bitmap_height = 312
    img = create_label_image(text, bitmap_width, bitmap_height)

    # Save preview
    img.save("label_preview.png")
    print(f"Preview saved: label_preview.png ({img.width}x{img.height})")

    # Convert to TSPL bitmap format
    width_bytes = (bitmap_width + 7) // 8
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
        if bit_pos != 7:
            bitmap_data.append(row_byte)
        while len(bitmap_data) % width_bytes != 0:
            bitmap_data.append(0xFF)

    # Dither solid black regions (thermal protection)
    for i in range(len(bitmap_data)):
        if bitmap_data[i] == 0x00 and i % 4 == 0:
            bitmap_data[i] = 0x08

    print(f"Bitmap: {width_bytes}x{bitmap_height} = {len(bitmap_data)} bytes")

    # Scan for printer first
    address = await scan_for_printer()
    if not address:
        return False

    # Connect
    conn = BLEConnection()
    print(f"Connecting to {address}...")

    if not await conn.connect(address):
        print("Failed to connect!")
        return False
    
    print("Connected!")
    
    try:
        x_offset = 0  # Full width bitmap (96px)
        y_offset = 0  # Start at top edge (verified optimal)
        
        commands = []
        commands.append(b"SIZE 10 mm,40 mm\r\n")
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
        print(f"Sending with MTU: {mtu}")
        
        success = await conn.write_chunked(job_data, chunk_size=mtu)
        
        if success:
            print("Print job sent successfully!")
        else:
            print("Print job failed!")
        
        return success
        
    finally:
        await conn.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "HELLO"
    asyncio.run(print_label(text))
