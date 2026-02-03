#!/usr/bin/env python3
"""
P31S Printer Discovery Tool.

Scans for P31S printers and dumps their GATT services and characteristics.
This is the first step in protocol reverse engineering.

Usage:
    python tools/discover.py
    python tools/discover.py --address XX:XX:XX:XX:XX:XX
"""

import argparse
import asyncio
import sys

from bleak import BleakClient, BleakScanner


DEVICE_PATTERNS = ["P31", "POLONO", "MAKEID", "NIIMBOT", "LABEL"]


async def scan_devices(timeout: float = 10.0):
    """Scan for potential label printers."""
    print(f"Scanning for devices ({timeout}s)...")
    discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)

    printers = []
    print(f"\nFound {len(discovered)} total BLE devices\n")

    for address, (device, adv_data) in discovered.items():
        name = device.name or adv_data.local_name or "Unknown"
        is_printer = any(p.upper() in name.upper() for p in DEVICE_PATTERNS)

        if is_printer:
            printers.append(device)
            print(f"  [MATCH] {name}")
            print(f"          Address: {address}")
            print(f"          RSSI: {adv_data.rssi} dB")
            print()

    if not printers:
        print("No matching printers found.")
        print(f"Looked for patterns: {DEVICE_PATTERNS}")
        print("\nAll devices found:")
        sorted_devices = sorted(
            discovered.items(),
            key=lambda x: x[1][1].rssi or -100,
            reverse=True
        )
        for address, (device, adv_data) in sorted_devices[:10]:
            name = device.name or adv_data.local_name or "Unknown"
            print(f"  {name} [{address}] RSSI: {adv_data.rssi}")

    return printers


async def discover_services(address: str):
    """Connect to a device and discover all services."""
    print(f"Connecting to {address}...")

    try:
        async with BleakClient(address, timeout=20.0) as client:
            print(f"Connected: {client.is_connected}\n")
            print("=" * 60)
            print("GATT SERVICES AND CHARACTERISTICS")
            print("=" * 60)

            for service in client.services:
                print(f"\nService: {service.uuid}")
                print(f"         {get_service_name(service.uuid)}")

                for char in service.characteristics:
                    props = ", ".join(char.properties)
                    print(f"\n    Characteristic: {char.uuid}")
                    print(f"                    Handle: 0x{char.handle:04X}")
                    print(f"                    Properties: [{props}]")

                    # Try to read if readable
                    if "read" in char.properties:
                        try:
                            value = await client.read_gatt_char(char.uuid)
                            print(f"                    Value: {value.hex()}")
                            # Try to decode as string
                            try:
                                text = value.decode("utf-8", errors="replace")
                                if text.isprintable():
                                    print(f"                    Text: {text}")
                            except Exception:
                                pass
                        except Exception as e:
                            print(f"                    Read error: {e}")

                    # List descriptors
                    for desc in char.descriptors:
                        print(f"        Descriptor: {desc.uuid}")

            print("\n" + "=" * 60)
            print("DISCOVERY COMPLETE")
            print("=" * 60)

            # Summary
            write_chars = []
            notify_chars = []

            for service in client.services:
                for char in service.characteristics:
                    if "write" in char.properties or "write-without-response" in char.properties:
                        write_chars.append(char.uuid)
                    if "notify" in char.properties or "indicate" in char.properties:
                        notify_chars.append(char.uuid)

            print("\nSUMMARY:")
            print(f"  Write characteristics: {len(write_chars)}")
            for uuid in write_chars:
                print(f"    - {uuid}")
            print(f"  Notify characteristics: {len(notify_chars)}")
            for uuid in notify_chars:
                print(f"    - {uuid}")

    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)


def get_service_name(uuid: str) -> str:
    """Get human-readable name for known service UUIDs."""
    known = {
        "00001800-0000-1000-8000-00805f9b34fb": "Generic Access",
        "00001801-0000-1000-8000-00805f9b34fb": "Generic Attribute",
        "0000180a-0000-1000-8000-00805f9b34fb": "Device Information",
        "0000180f-0000-1000-8000-00805f9b34fb": "Battery Service",
        "6e400001-b5a3-f393-e0a9-e50e24dcca9e": "Nordic UART Service",
        "49535343-fe7d-4ae5-8fa9-9fafd205e455": "Microchip UART Service",
    }
    return known.get(uuid.lower(), "Unknown/Vendor Specific")


async def main():
    parser = argparse.ArgumentParser(description="P31S Printer Discovery Tool")
    parser.add_argument(
        "--address", "-a",
        help="Connect directly to this address"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float, default=10.0,
        help="Scan timeout in seconds"
    )
    args = parser.parse_args()

    if args.address:
        await discover_services(args.address)
    else:
        printers = await scan_devices(args.timeout)
        if printers:
            print("\nTo discover services, run:")
            print(f"  python tools/discover.py -a {printers[0].address}")


if __name__ == "__main__":
    asyncio.run(main())
