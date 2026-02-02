#!/usr/bin/env python3
"""
Test script for P31S status commands.

This script connects to a P31S printer via BLE and tests the text-based
status commands (CONFIG?, BATTERY?) to verify the protocol implementation.

Usage:
    python test_status_commands.py [--address ADDRESS]

If no address is provided, the script will scan for available printers.
"""

import argparse
import asyncio
import sys

from src.p31sprinter.connection import BLEConnection
from src.p31sprinter.tspl_commands import TSPLCommands
from src.p31sprinter.responses import PrinterConfig, BatteryStatus


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


async def test_config_command(conn: BLEConnection) -> bool:
    """Test CONFIG? command."""
    print("\n" + "=" * 50)
    print("Testing CONFIG? command")
    print("=" * 50)

    cmd = TSPLCommands.config_query()
    print(f"Sending: {cmd!r}")

    success = await conn.write(cmd)
    if not success:
        print("Failed to send command")
        return False

    response = await conn.read_response(timeout=5.0)
    if not response:
        print("No response received (timeout)")
        return False

    print(f"Response ({len(response)} bytes): {response.hex()}")
    print(f"Raw bytes: {list(response)}")

    # Try to parse the response
    config = PrinterConfig.parse(response)
    if config:
        print("\nParsed successfully:")
        print(config)
        return True
    else:
        print("\nFailed to parse response")
        print("Expected: 19 or 20 bytes ending with CRLF")
        return False


async def test_battery_command(conn: BLEConnection) -> bool:
    """Test BATTERY? command."""
    print("\n" + "=" * 50)
    print("Testing BATTERY? command")
    print("=" * 50)

    cmd = TSPLCommands.battery_query()
    print(f"Sending: {cmd!r}")

    success = await conn.write(cmd)
    if not success:
        print("Failed to send command")
        return False

    response = await conn.read_response(timeout=5.0)
    if not response:
        print("No response received (timeout)")
        return False

    print(f"Response ({len(response)} bytes): {response.hex()}")
    print(f"Raw bytes: {list(response)}")
    if response[:7] == b"BATTERY":
        print(f"ASCII header: {response[:7].decode('ascii')}")

    # Try to parse the response
    battery = BatteryStatus.parse(response)
    if battery:
        print("\nParsed successfully:")
        print(battery)
        return True
    else:
        print("\nFailed to parse response")
        print("Expected: 11 or 12 bytes starting with 'BATTERY'")
        return False


async def test_binary_protocol(conn: BLEConnection) -> None:
    """
    Test if the printer responds to binary NIIMBOT protocol.

    This is to verify which protocol the printer actually uses.
    """
    print("\n" + "=" * 50)
    print("Testing binary protocol (NIIMBOT-style)")
    print("=" * 50)

    # Import binary protocol
    from src.p31sprinter.protocol import Packet, PacketType

    # Try GET_INFO command
    cmd = Packet(PacketType.GET_INFO, b"").encode()
    print(f"Sending GET_INFO: {cmd.hex()}")

    success = await conn.write(cmd)
    if not success:
        print("Failed to send command")
        return

    response = await conn.read_response(timeout=3.0)
    if not response:
        print("No response (may not support binary protocol)")
    else:
        print(f"Response: {response.hex()}")
        # Check if it looks like a valid binary response
        if response[:2] == bytes([0x55, 0x55]):
            print("Response has NIIMBOT header - printer may support binary protocol")
        else:
            print("Response does not have binary header")


async def test_initialize_command(conn: BLEConnection) -> bool:
    """Test INITIALPRINTER command."""
    print("\n" + "=" * 50)
    print("Testing INITIALPRINTER command")
    print("=" * 50)

    cmd = TSPLCommands.initialize()
    print(f"Sending: {cmd!r}")

    success = await conn.write(cmd)
    if not success:
        print("Failed to send command")
        return False

    # This command may not return a response
    response = await conn.read_response(timeout=2.0)
    if response:
        print(f"Response ({len(response)} bytes): {response.hex()}")
    else:
        print("No response (this may be normal for initialization)")

    return True


async def main(address: str | None = None):
    """Main test routine."""
    print("P31S Status Command Test")
    print("=" * 50)

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

    try:
        # Print discovered characteristics
        services = await conn.get_services()
        print("\nDiscovered services:")
        for svc in services:
            print(f"  Service: {svc.service_uuid}")
            for char in svc.characteristics:
                print(f"    Char: {char['uuid']} - {char['properties']}")

        # Run tests
        results = []

        # Test text-based commands
        results.append(("CONFIG?", await test_config_command(conn)))

        # Small delay between commands
        await asyncio.sleep(0.5)

        results.append(("BATTERY?", await test_battery_command(conn)))

        await asyncio.sleep(0.5)

        # Test initialization
        results.append(("INITIALPRINTER", await test_initialize_command(conn)))

        await asyncio.sleep(0.5)

        # Also test binary protocol for comparison
        await test_binary_protocol(conn)

        # Summary
        print("\n" + "=" * 50)
        print("Test Summary")
        print("=" * 50)
        for name, success in results:
            status = "PASS" if success else "FAIL"
            print(f"  {name}: {status}")

    finally:
        print("\nDisconnecting...")
        await conn.disconnect()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test P31S status commands")
    parser.add_argument("--address", "-a", help="Printer BLE address")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args.address)))
