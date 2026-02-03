#!/usr/bin/env python3
"""
Generate and print hard drive labels from smartctl output.

Usage:
    # Print labels from individual smartctl files:
    python generate_labels.py smart.sda smart.sdb smart.sdc

    # Print labels from concatenated smartctl output:
    cat smart.sd* > all_drives.txt
    python generate_labels.py all_drives.txt

    # Preview only (no printing):
    python generate_labels.py --preview-only smart.sda

The script parses smartctl -a output and prints labels with:
- Drive capacity (e.g., 8TB)
- Vendor and model
- Serial number (white on black, prominently displayed)
"""

import asyncio
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")
from PIL import Image, ImageDraw, ImageFont
from p31s.connection import BLEConnection


def parse_smartctl_text(content: str) -> dict | None:
    """Parse a single smartctl output block and extract drive info."""
    # Extract vendor
    vendor_match = re.search(r'^Vendor:\s+(.+)$', content, re.MULTILINE)
    vendor = vendor_match.group(1).strip() if vendor_match else ""

    # Extract product/model
    product_match = re.search(r'^Product:\s+(.+)$', content, re.MULTILINE)
    product = product_match.group(1).strip() if product_match else ""

    # Extract serial number
    serial_match = re.search(r'^Serial number:\s+(.+)$', content, re.MULTILINE)
    serial = serial_match.group(1).strip() if serial_match else ""

    # Extract capacity - look for the human-readable format like [8.00 TB]
    capacity_match = re.search(r'User Capacity:.*\[([^\]]+)\]', content)
    if capacity_match:
        capacity = capacity_match.group(1).strip()
        # Convert to whole units (e.g., "8.00 TB" -> "8TB")
        cap_num_match = re.match(r'([\d.]+)\s*(\w+)', capacity)
        if cap_num_match:
            num = float(cap_num_match.group(1))
            unit = cap_num_match.group(2)
            capacity = f"{int(num)}{unit}"
    else:
        capacity = ""

    # Skip if we didn't find essential info
    if not serial:
        return None

    return {
        'vendor': vendor,
        'product': product,
        'serial': serial,
        'capacity': capacity,
    }


def parse_smartctl_file(filepath: Path) -> list[dict]:
    """Parse smartctl file(s) and return list of drive info dicts.

    Handles both single-drive files and concatenated multi-drive files.
    """
    content = filepath.read_text()

    # Split on smartctl header to handle concatenated files
    # Each drive's output starts with "smartctl X.X"
    blocks = re.split(r'(?=smartctl \d+\.\d+)', content)

    drives = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        drive_info = parse_smartctl_text(block)
        if drive_info:
            drives.append(drive_info)

    return drives


def load_font(size: int, bold: bool = False):
    """Load a font with fallbacks for different platforms."""
    if bold:
        fonts = ['/System/Library/Fonts/Helvetica.ttc',
                 '/System/Library/Fonts/SFCompact.ttf',
                 'DejaVuSans-Bold.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
    else:
        fonts = ['/System/Library/Fonts/Menlo.ttc',
                 '/System/Library/Fonts/Monaco.ttf',
                 'DejaVuSansMono-Bold.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf']
    for font_name in fonts:
        try:
            return ImageFont.truetype(font_name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def create_label_image(drive_info: dict) -> Image.Image:
    """Create a label image for a drive."""
    width, height = 320, 120
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)

    # Leave padding for unprintable edges
    pad_top = 6
    pad_bottom = 14  # Bottom edge gets cut off more

    capacity_font = load_font(36, bold=True)
    make_model_font = load_font(17)
    serial_font = load_font(38, bold=True)

    capacity = drive_info['capacity']
    vendor = drive_info['vendor']
    product = drive_info['product']
    serial = drive_info['serial']

    margin = 8
    top_section_height = pad_top + 42
    h_line_y = top_section_height + 3

    cap_bbox = draw.textbbox((0, 0), capacity, font=capacity_font)
    cap_width = cap_bbox[2] - cap_bbox[0]
    cap_height = cap_bbox[3] - cap_bbox[1]
    cap_x = margin + 8
    cap_y = pad_top + (top_section_height - pad_top - cap_height) // 2 - 2

    cap_section_width = cap_x + cap_width + 12
    text_x = cap_section_width + 10
    vendor_bbox = draw.textbbox((0, 0), vendor, font=make_model_font)
    product_bbox = draw.textbbox((0, 0), product, font=make_model_font)
    vendor_height = vendor_bbox[3] - vendor_bbox[1]
    product_height = product_bbox[3] - product_bbox[1]
    total_text_height = vendor_height + product_height + 8
    vendor_y = pad_top + (top_section_height - pad_top - total_text_height) // 2 - 4
    product_y = vendor_y + vendor_height + 8

    # Draw black rectangle for bottom section (serial area)
    bottom_rect_top = h_line_y
    draw.rectangle([(0, bottom_rect_top), (width, height)], fill='black')

    serial_bbox = draw.textbbox((0, 0), serial, font=serial_font)
    serial_width = serial_bbox[2] - serial_bbox[0]
    serial_x = (width - serial_width) // 2
    serial_y = bottom_rect_top + 6

    draw.text((cap_x, cap_y), capacity, fill='black', font=capacity_font)
    draw.text((text_x, vendor_y), vendor, fill='black', font=make_model_font)
    draw.text((text_x, product_y), product, fill='black', font=make_model_font)
    draw.text((serial_x, serial_y), serial, fill='white', font=serial_font)

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


async def print_image(img: Image.Image, conn: BLEConnection) -> bool:
    """Print an image to the P31S printer using existing connection."""
    # Rotate -90 degrees (clockwise) for portrait orientation (120x320)
    img_rotated = img.rotate(-90, expand=True)

    # Convert to 1-bit
    img_1bit = img_rotated.convert("1")

    bitmap_width = img_1bit.width   # 120
    bitmap_height = img_1bit.height  # 320

    # Convert to TSPL bitmap format
    width_bytes = (bitmap_width + 7) // 8
    bitmap_data = bytearray()

    for y in range(bitmap_height):
        row_byte = 0
        bit_pos = 7
        for x in range(bitmap_width):
            pixel = img_1bit.getpixel((x, y))
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

    commands = []
    commands.append(b"SIZE 14 mm,40 mm\r\n")
    commands.append(b"GAP 2 mm,0 mm\r\n")
    commands.append(b"DIRECTION 0,0\r\n")
    commands.append(b"DENSITY 12\r\n")
    commands.append(b"CLS\r\n")
    commands.append(f"BITMAP 0,0,{width_bytes},{bitmap_height},1,".encode())
    commands.append(bytes(bitmap_data))
    commands.append(b"\r\n")
    commands.append(b"PRINT 1\r\n")

    job_data = b"".join(commands)

    mtu = await conn.get_mtu()
    success = await conn.write_chunked(job_data, chunk_size=mtu)

    return success


async def main():
    parser = argparse.ArgumentParser(
        description='Generate and print hard drive labels from smartctl output.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('files', nargs='*', help='smartctl output file(s)')
    parser.add_argument('--preview-only', action='store_true',
                        help='Generate preview images without printing')
    args = parser.parse_args()

    # Find input files
    if args.files:
        input_files = [Path(f) for f in args.files]
    else:
        # Default: look for smart.sd* files
        input_files = sorted(Path('.').glob('smart.sd*'))

    if not input_files:
        print("No input files specified and no smart.sd* files found.")
        print("Usage: python generate_labels.py [smartctl_output_file ...]")
        sys.exit(1)

    # Parse all drives from all input files
    all_drives = []
    for input_file in input_files:
        if not input_file.exists():
            print(f"File not found: {input_file}")
            continue
        drives = parse_smartctl_file(input_file)
        all_drives.extend(drives)

    if not all_drives:
        print("No drive information found in input files.")
        sys.exit(1)

    print(f"Found {len(all_drives)} drive(s)")

    # Generate label images
    labels = []
    for drive in all_drives:
        print(f"  - {drive['capacity']} {drive['vendor']} {drive['product']}: {drive['serial']}")
        img = create_label_image(drive)
        labels.append((drive, img))

        # Save preview
        preview_path = f"label_{drive['serial']}.png"
        img.save(preview_path)
        print(f"    Preview: {preview_path}")

    if args.preview_only:
        print("Preview only mode - not printing.")
        return

    # Connect to printer once and print all labels
    address = await scan_for_printer()
    if not address:
        print("Cannot print - no printer found.")
        sys.exit(1)

    conn = BLEConnection()
    print(f"Connecting to {address}...")

    if not await conn.connect(address):
        print("Failed to connect!")
        sys.exit(1)

    print("Connected!")

    try:
        for i, (drive, img) in enumerate(labels):
            print(f"Printing label {i+1}/{len(labels)}: {drive['serial']}...")
            success = await print_image(img, conn)
            if success:
                print(f"  Sent!")
            else:
                print(f"  Failed!")
                continue

            # Wait for printer to finish before next label
            if i < len(labels) - 1:
                await asyncio.sleep(4.0)
    finally:
        await conn.disconnect()
        print("Disconnected")


if __name__ == '__main__':
    asyncio.run(main())
