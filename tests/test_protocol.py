"""Tests for P31S protocol implementation."""

import pytest

from p31printer.protocol import Packet, PacketType, CatPrinterPacket


class TestPacket:
    """Test NIIMBOT-style packet encoding/decoding."""

    def test_encode_simple(self):
        """Test encoding a simple packet."""
        packet = Packet(command=0xC1, data=b"\x01")
        encoded = packet.encode()

        # Expected: HEAD(55 55) + CMD(C1) + LEN(01) + DATA(01) + CHECKSUM + TAIL(AA AA)
        assert encoded[:2] == bytes([0x55, 0x55])  # Head
        assert encoded[2] == 0xC1  # Command
        assert encoded[3] == 0x01  # Data length
        assert encoded[4] == 0x01  # Data
        assert encoded[-2:] == bytes([0xAA, 0xAA])  # Tail

        # Verify checksum: XOR of C1, 01, 01 = C1
        expected_checksum = 0xC1 ^ 0x01 ^ 0x01
        assert encoded[5] == expected_checksum

    def test_encode_empty_data(self):
        """Test encoding a packet with no data."""
        packet = Packet(command=0x40, data=b"")
        encoded = packet.encode()

        assert encoded[:2] == bytes([0x55, 0x55])
        assert encoded[2] == 0x40
        assert encoded[3] == 0x00  # Length = 0
        # Checksum = 0x40 ^ 0x00 = 0x40
        assert encoded[4] == 0x40
        assert encoded[-2:] == bytes([0xAA, 0xAA])

    def test_encode_longer_data(self):
        """Test encoding a packet with multiple data bytes."""
        packet = Packet(command=0x13, data=bytes([0x60, 0x00, 0x80, 0x00]))
        encoded = packet.encode()

        assert encoded[2] == 0x13
        assert encoded[3] == 0x04  # Length = 4
        assert encoded[4:8] == bytes([0x60, 0x00, 0x80, 0x00])

    def test_decode_simple(self):
        """Test decoding a valid packet."""
        # Build a valid packet manually
        data = bytes([0x55, 0x55, 0xC1, 0x01, 0x01, 0xC1, 0xAA, 0xAA])
        packet = Packet.decode(data)

        assert packet is not None
        assert packet.command == 0xC1
        assert packet.data == b"\x01"

    def test_decode_invalid_head(self):
        """Test decoding rejects invalid head."""
        data = bytes([0x00, 0x00, 0xC1, 0x01, 0x01, 0xC1, 0xAA, 0xAA])
        packet = Packet.decode(data)
        assert packet is None

    def test_decode_invalid_tail(self):
        """Test decoding rejects invalid tail."""
        data = bytes([0x55, 0x55, 0xC1, 0x01, 0x01, 0xC1, 0x00, 0x00])
        packet = Packet.decode(data)
        assert packet is None

    def test_decode_invalid_checksum(self):
        """Test decoding rejects invalid checksum."""
        data = bytes([0x55, 0x55, 0xC1, 0x01, 0x01, 0xFF, 0xAA, 0xAA])
        packet = Packet.decode(data)
        assert packet is None

    def test_decode_too_short(self):
        """Test decoding rejects too-short data."""
        data = bytes([0x55, 0x55, 0xC1])
        packet = Packet.decode(data)
        assert packet is None

    def test_roundtrip(self):
        """Test encode/decode roundtrip."""
        original = Packet(command=0x85, data=bytes([0xFF, 0x00, 0xAA, 0x55]))
        encoded = original.encode()
        decoded = Packet.decode(encoded)

        assert decoded is not None
        assert decoded.command == original.command
        assert decoded.data == original.data


class TestCatPrinterPacket:
    """Test Cat Printer-style packet encoding."""

    def test_crc8(self):
        """Test CRC8 calculation."""
        # Known test vectors
        assert CatPrinterPacket.crc8(b"") == 0x00
        assert CatPrinterPacket.crc8(b"\x00") == 0x00
        assert CatPrinterPacket.crc8(b"\x01") == 0x07

    def test_encode_simple(self):
        """Test encoding a Cat Printer packet."""
        encoded = CatPrinterPacket.encode(0xA4, bytes([0x02]))

        assert encoded[0] == 0x51  # Magic 0
        assert encoded[1] == 0x78  # Magic 1
        assert encoded[2] == 0xA4  # Command
        assert encoded[3] == 0x00  # Always zero
        assert encoded[4] == 0x01  # Data length
        assert encoded[5] == 0x00  # Always zero
        assert encoded[6] == 0x02  # Data
        # CRC8 and 0xFF tail
        assert encoded[-1] == 0xFF

    def test_encode_empty(self):
        """Test encoding with no data."""
        encoded = CatPrinterPacket.encode(0xA3, b"")

        assert encoded[4] == 0x00  # Length = 0
        assert len(encoded) == 8  # 6 header + CRC + 0xFF


class TestPacketType:
    """Test PacketType enum values."""

    def test_known_commands(self):
        """Verify expected command values."""
        assert PacketType.CONNECT == 0xC1
        assert PacketType.HEARTBEAT == 0xDC
        assert PacketType.PRINT_START == 0x01
        assert PacketType.PRINT_BITMAP_ROW == 0x85
        assert PacketType.PRINT_EMPTY_ROWS == 0x84
