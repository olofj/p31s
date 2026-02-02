#!/usr/bin/env python3
"""
Test script for P31S TSPL print commands.

Tries various TSPL command sequences to see what the printer responds to.
"""

import argparse
import asyncio
import sys

from src.p31printer.connection import BLEConnection
from src.p31printer.tspl_commands import TSPLCommands


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


def make_tspl_command(cmd: str) -> bytes:
    """Convert a TSPL command string to bytes with CRLF."""
    return cmd.encode("utf-8") + b"\r\n"


async def send_and_wait(conn: BLEConnection, cmd: bytes, description: str, wait_time: float = 2.0) -> bytes | None:
    """Send a command and wait for response."""
    print(f"\n>>> Sending: {description}")
    print(f"    Raw: {cmd!r}")

    success = await conn.write(cmd)
    if not success:
        print("    FAILED to send")
        return None

    print("    Sent OK, waiting for response...")
    response = await conn.read_response(timeout=wait_time)

    if response:
        print(f"    Response ({len(response)} bytes): {response.hex()}")
        # Try to decode as ASCII if printable
        try:
            if all(32 <= b < 127 or b in (10, 13) for b in response):
                print(f"    ASCII: {response.decode('ascii')!r}")
        except:
            pass
    else:
        print("    No response (timeout)")

    return response


async def test_initialization(conn: BLEConnection):
    """Test initialization commands."""
    print("\n" + "=" * 60)
    print("TEST 1: Initialization Commands")
    print("=" * 60)

    # Try INITIALPRINTER
    await send_and_wait(conn, TSPLCommands.initialize(), "INITIALPRINTER")
    await asyncio.sleep(0.5)

    # Try getting chunk size
    await send_and_wait(conn, TSPLCommands.get_chunk_size(), "GETCHUNKSIZE")
    await asyncio.sleep(0.5)


async def test_basic_tspl(conn: BLEConnection):
    """Test basic TSPL commands one at a time."""
    print("\n" + "=" * 60)
    print("TEST 2: Basic TSPL Commands (one at a time)")
    print("=" * 60)

    commands = [
        ("SIZE 15 mm,12 mm", "Set label size 15x12mm"),
        ("GAP 2 mm,0 mm", "Set gap 2mm"),
        ("DENSITY 8", "Set density to 8"),
        ("DIRECTION 0,0", "Set direction"),
        ("CLS", "Clear buffer"),
    ]

    for cmd, desc in commands:
        await send_and_wait(conn, make_tspl_command(cmd), f"{desc} [{cmd}]")
        await asyncio.sleep(0.3)


async def test_simple_print(conn: BLEConnection):
    """Test a simple print job - just a black bar."""
    print("\n" + "=" * 60)
    print("TEST 3: Simple Print Job (black bar)")
    print("=" * 60)

    # Send commands one at a time
    commands = [
        "SIZE 15 mm,12 mm",
        "GAP 2 mm,0 mm",
        "DENSITY 8",
        "CLS",
        "BAR 20,20,60,60",  # Draw a 60x60 dot black square
        "PRINT 1,1",
    ]

    for cmd in commands:
        await send_and_wait(conn, make_tspl_command(cmd), cmd, wait_time=1.0)
        await asyncio.sleep(0.3)

    print("\n    Waiting for print to complete...")
    await asyncio.sleep(3.0)


async def test_batch_tspl(conn: BLEConnection):
    """Test sending all TSPL commands as a single batch."""
    print("\n" + "=" * 60)
    print("TEST 4: Batch TSPL Commands (all at once)")
    print("=" * 60)

    # Build complete command sequence
    commands = [
        "SIZE 15 mm,12 mm",
        "GAP 2 mm,0 mm",
        "DENSITY 8",
        "CLS",
        "BAR 20,20,60,60",
        "PRINT 1,1",
    ]

    batch = b"".join(make_tspl_command(cmd) for cmd in commands)
    print(f"Batch size: {len(batch)} bytes")

    await send_and_wait(conn, batch, "Complete print job batch", wait_time=3.0)

    print("\n    Waiting for print to complete...")
    await asyncio.sleep(3.0)


async def test_selftest(conn: BLEConnection):
    """Test the SELFTEST command."""
    print("\n" + "=" * 60)
    print("TEST 5: Self-Test Print")
    print("=" * 60)

    await send_and_wait(conn, TSPLCommands.selftest(), "SELFTEST", wait_time=5.0)

    print("\n    Waiting for self-test to complete...")
    await asyncio.sleep(5.0)


async def test_alternate_characteristics(conn: BLEConnection):
    """Try writing to different characteristics."""
    print("\n" + "=" * 60)
    print("TEST 6: Try Alternate Characteristics")
    print("=" * 60)

    if not conn.client:
        print("Not connected")
        return

    # Get all writable characteristics
    write_chars = []
    for service in conn.client.services:
        for char in service.characteristics:
            if "write" in char.properties or "write-without-response" in char.properties:
                write_chars.append((service.uuid, char.uuid))

    print(f"Found {len(write_chars)} writable characteristics:")
    for svc, char in write_chars:
        print(f"  Service {svc} -> Char {char}")

    # Try each one with a simple command
    cmd = TSPLCommands.config_query()
    original_write_char = conn.write_char

    for svc, char in write_chars:
        if char == original_write_char:
            print(f"\n  Skipping {char} (already tested)")
            continue

        print(f"\n  Trying characteristic: {char}")
        conn.write_char = char

        try:
            success = await conn.write(cmd)
            if success:
                print(f"    Write succeeded, waiting for response...")
                response = await conn.read_response(timeout=2.0)
                if response:
                    print(f"    Got response: {response.hex()}")
                else:
                    print(f"    No response")
            else:
                print(f"    Write failed")
        except Exception as e:
            print(f"    Error: {e}")

    # Restore original
    conn.write_char = original_write_char


async def main(address: str | None = None, test: str = "all"):
    """Main test routine."""
    print("P31S TSPL Print Command Test")
    print("=" * 60)

    # Get printer address
    if not address:
        address = await scan_and_select()
        if not address:
            return 1

    # Connect
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

        if test == "all" or test == "init":
            await test_initialization(conn)

        if test == "all" or test == "basic":
            await test_basic_tspl(conn)

        if test == "all" or test == "print":
            await test_simple_print(conn)

        if test == "all" or test == "batch":
            await test_batch_tspl(conn)

        if test == "all" or test == "selftest":
            await test_selftest(conn)

        if test == "all" or test == "chars":
            await test_alternate_characteristics(conn)

    finally:
        print("\n" + "=" * 60)
        print("Disconnecting...")
        await conn.disconnect()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test P31S TSPL print commands")
    parser.add_argument("--address", "-a", help="Printer BLE address")
    parser.add_argument("--test", "-t",
                        choices=["all", "init", "basic", "print", "batch", "selftest", "chars"],
                        default="all",
                        help="Which test to run (default: all)")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args.address, args.test)))
