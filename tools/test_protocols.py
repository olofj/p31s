#!/usr/bin/env python3
"""
Protocol Testing Tool.

Tests various known thermal printer protocols against the P31S.
Run this after discovering the write characteristic UUID.

Usage:
    python tools/test_protocols.py ADDRESS
    python tools/test_protocols.py ADDRESS --write-uuid UUID --notify-uuid UUID
"""

import argparse
import asyncio
import sys

from bleak import BleakClient


# NIIMBOT-style packet
def make_niimbot_packet(cmd: int, data: bytes = b"") -> bytes:
    """Build a NIIMBOT-style packet."""
    packet = bytes([0x55, 0x55, cmd, len(data)]) + data
    checksum = 0
    for b in packet[2:]:
        checksum ^= b
    return packet + bytes([checksum, 0xAA, 0xAA])


# Cat Printer-style packet
CRC8_TABLE = [
    0x00, 0x07, 0x0e, 0x09, 0x1c, 0x1b, 0x12, 0x15,
    0x38, 0x3f, 0x36, 0x31, 0x24, 0x23, 0x2a, 0x2d,
    0x70, 0x77, 0x7e, 0x79, 0x6c, 0x6b, 0x62, 0x65,
    0x48, 0x4f, 0x46, 0x41, 0x54, 0x53, 0x5a, 0x5d,
    0xe0, 0xe7, 0xee, 0xe9, 0xfc, 0xfb, 0xf2, 0xf5,
    0xd8, 0xdf, 0xd6, 0xd1, 0xc4, 0xc3, 0xca, 0xcd,
    0x90, 0x97, 0x9e, 0x99, 0x8c, 0x8b, 0x82, 0x85,
    0xa8, 0xaf, 0xa6, 0xa1, 0xb4, 0xb3, 0xba, 0xbd,
    0xc7, 0xc0, 0xc9, 0xce, 0xdb, 0xdc, 0xd5, 0xd2,
    0xff, 0xf8, 0xf1, 0xf6, 0xe3, 0xe4, 0xed, 0xea,
    0xb7, 0xb0, 0xb9, 0xbe, 0xab, 0xac, 0xa5, 0xa2,
    0x8f, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9d, 0x9a,
    0x27, 0x20, 0x29, 0x2e, 0x3b, 0x3c, 0x35, 0x32,
    0x1f, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0d, 0x0a,
    0x57, 0x50, 0x59, 0x5e, 0x4b, 0x4c, 0x45, 0x42,
    0x6f, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7d, 0x7a,
    0x89, 0x8e, 0x87, 0x80, 0x95, 0x92, 0x9b, 0x9c,
    0xb1, 0xb6, 0xbf, 0xb8, 0xad, 0xaa, 0xa3, 0xa4,
    0xf9, 0xfe, 0xf7, 0xf0, 0xe5, 0xe2, 0xeb, 0xec,
    0xc1, 0xc6, 0xcf, 0xc8, 0xdd, 0xda, 0xd3, 0xd4,
    0x69, 0x6e, 0x67, 0x60, 0x75, 0x72, 0x7b, 0x7c,
    0x51, 0x56, 0x5f, 0x58, 0x4d, 0x4a, 0x43, 0x44,
    0x19, 0x1e, 0x17, 0x10, 0x05, 0x02, 0x0b, 0x0c,
    0x21, 0x26, 0x2f, 0x28, 0x3d, 0x3a, 0x33, 0x34,
    0x4e, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5c, 0x5b,
    0x76, 0x71, 0x78, 0x7f, 0x6a, 0x6d, 0x64, 0x63,
    0x3e, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2c, 0x2b,
    0x06, 0x01, 0x08, 0x0f, 0x1a, 0x1d, 0x14, 0x13,
    0xae, 0xa9, 0xa0, 0xa7, 0xb2, 0xb5, 0xbc, 0xbb,
    0x96, 0x91, 0x98, 0x9f, 0x8a, 0x8d, 0x84, 0x83,
    0xde, 0xd9, 0xd0, 0xd7, 0xc2, 0xc5, 0xcc, 0xcb,
    0xe6, 0xe1, 0xe8, 0xef, 0xfa, 0xfd, 0xf4, 0xf3,
]


def crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc = CRC8_TABLE[(crc ^ byte) & 0xFF]
    return crc


def make_cat_packet(cmd: int, data: bytes = b"") -> bytes:
    """Build a Cat Printer-style packet."""
    packet = bytes([0x51, 0x78, cmd, 0x00, len(data), 0x00]) + data
    return packet + bytes([crc8(data), 0xFF])


# ESC/POS-style commands
def make_escpos_init() -> bytes:
    """ESC/POS initialize command."""
    return bytes([0x1B, 0x40])  # ESC @


def make_phomemo_init() -> bytes:
    """Phomemo D30-style init."""
    return bytes.fromhex("1f1124001b40")


class ProtocolTester:
    """Tests various protocols against the printer."""

    def __init__(self, address: str, write_uuid: str = None, notify_uuid: str = None):
        self.address = address
        self.write_uuid = write_uuid
        self.notify_uuid = notify_uuid
        self.responses = []

    def _notification_handler(self, sender, data):
        """Handle incoming notifications."""
        print(f"  <- RX: {data.hex()}")
        self.responses.append(bytes(data))

    async def test(self):
        """Run all protocol tests."""
        print(f"Connecting to {self.address}...")

        async with BleakClient(self.address, timeout=20.0) as client:
            print(f"Connected: {client.is_connected}\n")

            # Find write/notify characteristics if not specified
            if not self.write_uuid or not self.notify_uuid:
                for service in client.services:
                    for char in service.characteristics:
                        if not self.write_uuid and ("write" in char.properties or
                                                     "write-without-response" in char.properties):
                            self.write_uuid = char.uuid
                            print(f"Using write characteristic: {self.write_uuid}")
                        if not self.notify_uuid and ("notify" in char.properties or
                                                      "indicate" in char.properties):
                            self.notify_uuid = char.uuid
                            print(f"Using notify characteristic: {self.notify_uuid}")

            if not self.write_uuid:
                print("ERROR: No write characteristic found!")
                return

            # Enable notifications
            if self.notify_uuid:
                await client.start_notify(self.notify_uuid, self._notification_handler)
                print("Notifications enabled\n")

            # Run tests
            await self._test_niimbot(client)
            await self._test_cat_printer(client)
            await self._test_escpos(client)

            if self.notify_uuid:
                await client.stop_notify(self.notify_uuid)

    async def _send(self, client: BleakClient, data: bytes, description: str):
        """Send data and wait for response."""
        print(f"\n{description}")
        print(f"  -> TX: {data.hex()}")
        self.responses.clear()

        try:
            await client.write_gatt_char(self.write_uuid, data, response=False)
            await asyncio.sleep(0.5)  # Wait for response

            if not self.responses:
                print("  <- (no response)")
        except Exception as e:
            print(f"  <- ERROR: {e}")

    async def _test_niimbot(self, client: BleakClient):
        """Test NIIMBOT protocol."""
        print("\n" + "=" * 50)
        print("TESTING NIIMBOT PROTOCOL")
        print("=" * 50)

        # Connect command
        await self._send(
            client,
            make_niimbot_packet(0xC1, b"\x01"),
            "NIIMBOT Connect (0xC1)"
        )

        # Heartbeat
        await self._send(
            client,
            make_niimbot_packet(0xDC, b"\x01"),
            "NIIMBOT Heartbeat (0xDC)"
        )

        # Get device info
        await self._send(
            client,
            make_niimbot_packet(0x40, b""),
            "NIIMBOT Get Info (0x40)"
        )

        # Get serial number
        await self._send(
            client,
            make_niimbot_packet(0x1A, b""),
            "NIIMBOT Get Serial (0x1A)"
        )

    async def _test_cat_printer(self, client: BleakClient):
        """Test Cat Printer protocol."""
        print("\n" + "=" * 50)
        print("TESTING CAT PRINTER PROTOCOL")
        print("=" * 50)

        # Set quality
        await self._send(
            client,
            make_cat_packet(0xA4, bytes([0x02])),
            "Cat Printer Set Quality (0xA4)"
        )

        # Set energy
        await self._send(
            client,
            make_cat_packet(0xAF, bytes([0x50, 0x00])),
            "Cat Printer Set Energy (0xAF)"
        )

        # Get device state
        await self._send(
            client,
            make_cat_packet(0xA3, b""),
            "Cat Printer Get State (0xA3)"
        )

    async def _test_escpos(self, client: BleakClient):
        """Test ESC/POS protocol."""
        print("\n" + "=" * 50)
        print("TESTING ESC/POS PROTOCOL")
        print("=" * 50)

        # Standard ESC init
        await self._send(
            client,
            make_escpos_init(),
            "ESC/POS Init (ESC @)"
        )

        # Phomemo-style init
        await self._send(
            client,
            make_phomemo_init(),
            "Phomemo Init"
        )

        # Status request
        await self._send(
            client,
            bytes([0x10, 0x04, 0x01]),  # DLE EOT 1
            "ESC/POS Status (DLE EOT)"
        )


async def main():
    parser = argparse.ArgumentParser(description="Protocol Testing Tool")
    parser.add_argument("address", help="Printer Bluetooth address")
    parser.add_argument("--write-uuid", help="Write characteristic UUID")
    parser.add_argument("--notify-uuid", help="Notify characteristic UUID")
    args = parser.parse_args()

    tester = ProtocolTester(
        args.address,
        write_uuid=args.write_uuid,
        notify_uuid=args.notify_uuid
    )
    await tester.test()


if __name__ == "__main__":
    asyncio.run(main())
