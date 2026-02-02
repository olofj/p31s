#!/usr/bin/env python3
"""
Test script for P31S BITMAP print command.

Based on iOS BLE capture analysis:
- TSPL commands work via handles 0x0006 (write) / 0x0008 (notify)
- MTU is 124 bytes, so chunk size ~121 bytes
- BITMAP uses mode 1 (OR), not mode 0 (OVERWRITE)
- Write Without Response is used for commands

The P31S uses command type 0 (isPrintModelAfterSend) which is
standard TSPL with the following sequence:
1. SIZE
2. GAP
3. DIRECTION
4. DENSITY (optional)
5. CLS
6. BITMAP
7. PRINT
"""

import argparse
import asyncio
import sys

from src.p31printer.connection import BLEConnection
from src.p31printer.tspl_commands import TSPLCommands, BitmapMode


def create_test_pattern(width_pixels: int, height_pixels: int) -> bytes:
    """
    Create a simple test pattern bitmap.

    Creates a checkerboard pattern for testing.
    Each byte represents 8 horizontal pixels.

    Args:
        width_pixels: Width in pixels (will be rounded to byte boundary)
        height_pixels: Height in pixels

    Returns:
        Raw bitmap data (TSPL format: 0=black, 1=white)
    """
    width_bytes = (width_pixels + 7) // 8
    data = bytearray()

    for y in range(height_pixels):
        for x_byte in range(width_bytes):
            # Create checkerboard pattern
            if (y // 8 + x_byte) % 2 == 0:
                data.append(0xAA)  # 10101010 - alternating pixels
            else:
                data.append(0x55)  # 01010101 - alternating pixels

    return bytes(data)


def create_black_square(width_pixels: int, height_pixels: int) -> bytes:
    """
    Create a solid black square bitmap.

    NOTE: Solid black (all 0x00) may be rejected by the printer's
    thermal protection. Use create_dithered_black() instead.

    Args:
        width_pixels: Width in pixels
        height_pixels: Height in pixels

    Returns:
        Raw bitmap data (all zeros = all black)
    """
    width_bytes = (width_pixels + 7) // 8
    return bytes([0x00] * (width_bytes * height_pixels))


def create_fullpage_pattern(width_pixels: int, height_pixels: int) -> bytes:
    """
    Create a pattern that fills the entire label area.

    This ensures proper label feeding by having content across
    the full label dimensions.
    """
    width_bytes = (width_pixels + 7) // 8
    data = bytearray()

    for y in range(height_pixels):
        for x_byte in range(width_bytes):
            # Create a pattern based on position
            if y < 4 or y >= height_pixels - 4:
                # Top and bottom borders
                data.append(0x00 if (x_byte % 2 == 0) else 0xFF)
            elif x_byte == 0 or x_byte == width_bytes - 1:
                # Left and right edges
                data.append(0xAA)
            else:
                # Interior - light checkerboard
                if (y // 8 + x_byte) % 2 == 0:
                    data.append(0xAA)
                else:
                    data.append(0x55)

    return bytes(data)


def create_dithered_black(width_pixels: int, height_pixels: int) -> bytes:
    """
    Create a nearly-black pattern with minimal white pixels.

    Uses 0x00 and 0x08 alternating to have ~97% black coverage
    while avoiding the printer's thermal protection.

    Args:
        width_pixels: Width in pixels
        height_pixels: Height in pixels

    Returns:
        Raw bitmap data that appears mostly black
    """
    width_bytes = (width_pixels + 7) // 8
    data = bytearray()

    for y in range(height_pixels):
        for x_byte in range(width_bytes):
            # Alternate between pure black and black-with-one-white-pixel
            if (y + x_byte) % 4 == 0:
                data.append(0x08)  # 00001000 - one white pixel
            else:
                data.append(0x00)  # all black

    return bytes(data)


def create_simple_pattern(width_pixels: int, height_pixels: int) -> bytes:
    """
    Create a simple horizontal line pattern.

    Args:
        width_pixels: Width in pixels
        height_pixels: Height in pixels

    Returns:
        Raw bitmap data with alternating black/white horizontal lines
    """
    width_bytes = (width_pixels + 7) // 8
    data = bytearray()

    for y in range(height_pixels):
        if y % 2 == 0:
            # Black line (all zeros)
            data.extend([0x00] * width_bytes)
        else:
            # White line (all ones)
            data.extend([0xFF] * width_bytes)

    return bytes(data)


def create_gradient_pattern(width_pixels: int, height_pixels: int) -> bytes:
    """
    Create a gradient pattern with varying byte values.

    Uses different byte values (not just 0xAA/0x55) to test if
    specific patterns matter.
    """
    width_bytes = (width_pixels + 7) // 8
    data = bytearray()

    patterns = [0x80, 0xC0, 0xE0, 0xF0, 0xF8, 0xFC, 0xFE, 0xFF,
                0x7F, 0x3F, 0x1F, 0x0F, 0x07, 0x03, 0x01, 0x00]

    for y in range(height_pixels):
        pattern_idx = y % len(patterns)
        for x_byte in range(width_bytes):
            data.append(patterns[pattern_idx])

    return bytes(data)


def create_border_pattern(width_pixels: int, height_pixels: int, border: int = 4) -> bytes:
    """
    Create a border/frame pattern - white center with black border.

    This pattern has both 0x00 and 0xFF bytes which should work well
    with OR mode bitmap rendering.

    Args:
        width_pixels: Width in pixels
        height_pixels: Height in pixels
        border: Border thickness in pixels

    Returns:
        Raw bitmap data with black border, white center
    """
    width_bytes = (width_pixels + 7) // 8
    data = bytearray()

    for y in range(height_pixels):
        row = bytearray(width_bytes)
        for x in range(width_pixels):
            byte_idx = x // 8
            bit_idx = 7 - (x % 8)  # MSB first

            # Check if pixel is in border region
            in_border = (y < border or y >= height_pixels - border or
                        x < border or x >= width_pixels - border)

            if in_border:
                # Black pixel (bit = 0) - already 0, no action needed
                pass
            else:
                # White pixel (bit = 1)
                row[byte_idx] |= (1 << bit_idx)

        data.extend(row)

    return bytes(data)


async def scan_and_select() -> str | None:
    """Scan for printers and let user select one."""
    print("Scanning for P31S printers...")
    printers = await BLEConnection.scan(timeout=5.0)

    if not printers:
        print("No printers found.")
        return None

    print("\nFound printers:")
    for i, p in enumerate(printers):
        print(f"  [{i}] {p}")

    if len(printers) == 1:
        print(f"\nUsing: {printers[0].address}")
        return printers[0].address

    try:
        choice = int(input("\nSelect printer (number): "))
        return printers[choice].address
    except (ValueError, IndexError):
        print("Invalid selection.")
        return None


async def send_and_wait(conn: BLEConnection, cmd: bytes, description: str, wait_time: float = 2.0, use_chunked: bool = False, chunk_size: int = 20) -> bytes | None:
    """Send a command and wait for response."""
    print(f"\n>>> Sending: {description}")
    if len(cmd) < 100:
        print(f"    Raw: {cmd!r}")
    else:
        print(f"    Raw: {cmd[:50]!r}...({len(cmd)} bytes total)")

    if use_chunked and len(cmd) > chunk_size:
        print(f"    Using chunked write ({chunk_size} bytes/chunk)...")
        success = await conn.write_chunked(cmd, chunk_size=chunk_size, delay_ms=10)
    else:
        success = await conn.write(cmd)

    if not success:
        print("    FAILED to send")
        return None

    print("    Sent OK, waiting for response...")
    response = await conn.read_response(timeout=wait_time)

    if response:
        print(f"    Response ({len(response)} bytes): {response.hex()}")
        try:
            if all(32 <= b < 127 or b in (10, 13) for b in response):
                print(f"    ASCII: {response.decode('ascii')!r}")
        except:
            pass
    else:
        print("    No response (timeout)")

    return response


async def test_bitmap_print(conn: BLEConnection, pattern: str = "checker"):
    """Test BITMAP print command with various patterns."""
    print("\n" + "=" * 60)
    print("BITMAP Print Test")
    print("=" * 60)

    # Label size: 40mm x 10mm at 203 DPI
    # 40mm = ~320 pixels, 10mm = ~80 pixels
    label_width_mm = 40.0
    label_height_mm = 10.0
    gap_mm = 2.0
    density = 8

    # Bitmap dimensions
    # 40mm = ~320 pixels at 203 DPI, 10mm = ~80 pixels
    if pattern == "fullpage":
        # Full label coverage
        bitmap_width = 320  # Full 40mm width
        bitmap_height = 80   # Full 10mm height
        x_offset = 0
        y_offset = 0
        print("Creating full-page pattern (320x80 pixels)...")
        bitmap_data = create_fullpage_pattern(bitmap_width, bitmap_height)
    else:
        # Smaller test pattern
        bitmap_width = 64  # pixels
        bitmap_height = 64  # pixels
        x_offset = 128  # Centered: (320 - 64) / 2
        y_offset = 8    # Centered: (80 - 64) / 2

        if pattern == "black":
            print("Creating solid black square (may fail due to thermal protection)...")
            bitmap_data = create_black_square(bitmap_width, bitmap_height)
        elif pattern == "dithered":
            print("Creating dithered black (bypasses thermal protection)...")
            bitmap_data = create_dithered_black(bitmap_width, bitmap_height)
        elif pattern == "lines":
            print("Creating horizontal line pattern...")
            bitmap_data = create_simple_pattern(bitmap_width, bitmap_height)
        elif pattern == "border":
            print("Creating border/frame pattern...")
            bitmap_data = create_border_pattern(bitmap_width, bitmap_height)
        elif pattern == "gradient":
            print("Creating gradient pattern...")
            bitmap_data = create_gradient_pattern(bitmap_width, bitmap_height)
        else:
            print("Creating checkerboard pattern...")
            bitmap_data = create_test_pattern(bitmap_width, bitmap_height)

    bitmap_width_bytes = (bitmap_width + 7) // 8

    print(f"Bitmap: {bitmap_width}x{bitmap_height} pixels = {len(bitmap_data)} bytes")

    # Build the complete print job using the APK sequence
    print("\nBuilding print job (APK sequence):")
    print(f"  SIZE {label_width_mm} mm,{label_height_mm} mm")
    print(f"  GAP {gap_mm} mm,0 mm")
    print(f"  DIRECTION 0,0")
    print(f"  DENSITY {density}")
    print(f"  CLS")
    print(f"  BITMAP {x_offset},{y_offset},{bitmap_width_bytes},{bitmap_height},0,<{len(bitmap_data)} bytes>")
    print(f"  PRINT 1")

    # Get MTU info
    mtu = await conn.get_mtu()
    print(f"\nNegotiated MTU chunk size: {mtu} bytes")

    # Option 1: Use the helper function with chunked writes
    print("\n--- Sending complete print job (chunked) ---")
    print_job = TSPLCommands.build_print_job(
        width_mm=label_width_mm,
        height_mm=label_height_mm,
        gap_mm=gap_mm,
        density=density,
        bitmap_data=bitmap_data,
        bitmap_width_bytes=bitmap_width_bytes,
        bitmap_height=bitmap_height,
        x=x_offset,
        y=y_offset,
        copies=1,
    )

    print(f"Total command size: {len(print_job)} bytes")
    # Use chunked write for large data
    await send_and_wait(conn, print_job, "Complete BITMAP print job (chunked)",
                       wait_time=5.0, use_chunked=True, chunk_size=mtu)

    print("\nWaiting for print to complete...")
    await asyncio.sleep(5.0)


async def test_bitmap_step_by_step(conn: BLEConnection, pattern: str = "checker"):
    """Test BITMAP print by sending each command separately."""
    print("\n" + "=" * 60)
    print("BITMAP Print Test (Step-by-Step)")
    print("=" * 60)

    # Label size: 40mm x 10mm at 203 DPI
    label_width_mm = 40.0
    label_height_mm = 10.0
    gap_mm = 2.0
    density = 8

    # Create bitmap data
    if pattern == "fullpage":
        bitmap_width = 320
        bitmap_height = 80
        x_offset = 0
        y_offset = 0
        bitmap_data = create_fullpage_pattern(bitmap_width, bitmap_height)
    else:
        bitmap_width = 64
        bitmap_height = 64
        x_offset = 128
        y_offset = 8

        if pattern == "black":
            bitmap_data = create_black_square(bitmap_width, bitmap_height)
        elif pattern == "dithered":
            bitmap_data = create_dithered_black(bitmap_width, bitmap_height)
        elif pattern == "lines":
            bitmap_data = create_simple_pattern(bitmap_width, bitmap_height)
        elif pattern == "border":
            bitmap_data = create_border_pattern(bitmap_width, bitmap_height)
        elif pattern == "gradient":
            bitmap_data = create_gradient_pattern(bitmap_width, bitmap_height)
        else:
            bitmap_data = create_test_pattern(bitmap_width, bitmap_height)

    bitmap_width_bytes = (bitmap_width + 7) // 8

    print(f"Bitmap: {bitmap_width}x{bitmap_height} pixels = {len(bitmap_data)} bytes")

    # Send commands one at a time with delays
    mtu = await conn.get_mtu()
    print(f"MTU chunk size: {mtu} bytes")

    commands = [
        (TSPLCommands.size(label_width_mm, label_height_mm), "SIZE"),
        (TSPLCommands.gap(gap_mm, 0), "GAP"),
        (TSPLCommands.direction(0, 0), "DIRECTION"),
        (TSPLCommands.density(density), "DENSITY"),
        (TSPLCommands.cls(), "CLS"),
    ]

    for cmd, name in commands:
        await send_and_wait(conn, cmd, name)
        await asyncio.sleep(0.2)

    # Send BITMAP command (may need chunking)
    bitmap_cmd = TSPLCommands.bitmap(
        x_offset, y_offset, bitmap_width_bytes, bitmap_height,
        BitmapMode.OR, bitmap_data
    )
    print(f"\nBITMAP command size: {len(bitmap_cmd)} bytes")
    await send_and_wait(conn, bitmap_cmd, "BITMAP", wait_time=3.0,
                       use_chunked=True, chunk_size=mtu)
    await asyncio.sleep(0.5)

    # Send PRINT
    await send_and_wait(conn, TSPLCommands.print_label(1), "PRINT")

    print("\nWaiting for print to complete...")
    await asyncio.sleep(5.0)


async def test_individual_commands(conn: BLEConnection):
    """Test sending TSPL commands one at a time."""
    print("\n" + "=" * 60)
    print("Individual Command Test")
    print("=" * 60)

    commands = [
        (TSPLCommands.size(15.0, 12.0), "SIZE 15 mm,12 mm"),
        (TSPLCommands.gap(2.0, 0), "GAP 2 mm,0 mm"),
        (TSPLCommands.direction(0, 0), "DIRECTION 0,0"),
        (TSPLCommands.density(8), "DENSITY 8"),
        (TSPLCommands.cls(), "CLS"),
    ]

    for cmd, desc in commands:
        await send_and_wait(conn, cmd, desc)
        await asyncio.sleep(0.3)

    # Send a small bitmap
    bitmap_data = create_black_square(32, 32)
    bitmap_cmd = TSPLCommands.bitmap(40, 30, 4, 32, BitmapMode.OR, bitmap_data)
    await send_and_wait(conn, bitmap_cmd, f"BITMAP (32x32 black square, {len(bitmap_data)} bytes)")
    await asyncio.sleep(0.3)

    await send_and_wait(conn, TSPLCommands.print_label(1), "PRINT 1")

    print("\nWaiting for print...")
    await asyncio.sleep(5.0)


async def main(address: str | None = None, test: str = "bitmap", pattern: str = "checker"):
    """Main test routine."""
    print("P31S BITMAP Print Test")
    print("=" * 60)

    if not address:
        address = await scan_and_select()
        if not address:
            return 1

    conn = BLEConnection()
    print(f"\nConnecting to {address}...")

    if not await conn.connect(address):
        print("Connection failed")
        return 1

    print("Connected!")
    print(f"Write characteristic: {conn.write_char}")
    print(f"Notify characteristic: {conn.notify_char}")

    try:
        # Verify connection with CONFIG?
        print("\n--- Verifying connection with CONFIG? ---")
        response = await send_and_wait(conn, TSPLCommands.config_query(), "CONFIG?")
        if not response:
            print("WARNING: No response to CONFIG?, printer may not be ready")

        if test == "bitmap":
            await test_bitmap_print(conn, pattern)
        elif test == "stepbystep":
            await test_bitmap_step_by_step(conn, pattern)
        elif test == "individual":
            await test_individual_commands(conn)
        elif test == "selftest":
            await send_and_wait(conn, TSPLCommands.selftest(), "SELFTEST", wait_time=5.0)
            await asyncio.sleep(5.0)

    finally:
        print("\n" + "=" * 60)
        print("Disconnecting...")
        await conn.disconnect()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test P31S BITMAP print command")
    parser.add_argument("--address", "-a", help="Printer BLE address")
    parser.add_argument(
        "--test", "-t",
        choices=["bitmap", "stepbystep", "individual", "selftest"],
        default="bitmap",
        help="Which test to run (default: bitmap)"
    )
    parser.add_argument(
        "--pattern", "-p",
        choices=["checker", "black", "dithered", "lines", "border", "gradient", "fullpage"],
        default="checker",
        help="Bitmap pattern to print (default: checker)"
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args.address, args.test, args.pattern)))
