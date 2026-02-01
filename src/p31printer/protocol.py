"""
P31S Printer Protocol Implementation.

This module implements packet encoding/decoding for the P31S printer.
Protocol structure is based on reverse engineering of the Labelnize app
and testing against similar printers (NIIMBOT, Cat Printer).

Packet Structure (NIIMBOT-style, to be verified):
    Head:      0x55 0x55 (constant)
    Command:   0x00-0xFF (packet identifier)
    DataLen:   Number of data bytes
    Data:      Payload bytes
    Checksum:  XOR of bytes from Command through Data
    Tail:      0xAA 0xAA (constant)
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class PacketType(IntEnum):
    """Known command types (to be populated during reverse engineering)."""
    # Connection/Status
    CONNECT = 0xC1
    HEARTBEAT = 0xDC
    GET_INFO = 0x40

    # Print Job Control
    PRINT_START = 0x01
    PRINT_END = 0xF3
    PAGE_END = 0xE3

    # Label Configuration
    SET_LABEL_TYPE = 0x23
    SET_LABEL_DENSITY = 0x21
    SET_PAGE_SIZE = 0x13

    # Image Data
    PRINT_BITMAP_ROW = 0x85
    PRINT_BITMAP_ROW_INDEXED = 0x83
    PRINT_EMPTY_ROWS = 0x84

    # Paper Control
    FEED_PAPER = 0xA1  # Cat Printer style
    RETRACT_PAPER = 0xA0  # Cat Printer style


@dataclass
class Packet:
    """Represents a protocol packet."""
    command: int
    data: bytes = b""

    # Protocol constants (NIIMBOT-style, to be verified)
    HEAD = bytes([0x55, 0x55])
    TAIL = bytes([0xAA, 0xAA])

    def encode(self) -> bytes:
        """Encode packet to bytes for transmission."""
        # Build packet: HEAD + CMD + LEN + DATA + CHECKSUM + TAIL
        packet = self.HEAD + bytes([self.command, len(self.data)]) + self.data

        # XOR checksum over cmd, len, and data
        checksum = 0
        for b in packet[2:]:  # Skip HEAD bytes
            checksum ^= b

        return packet + bytes([checksum]) + self.TAIL

    @classmethod
    def decode(cls, data: bytes) -> Optional["Packet"]:
        """Decode bytes into a Packet object."""
        if len(data) < 7:  # Minimum: HEAD(2) + CMD(1) + LEN(1) + CHECKSUM(1) + TAIL(2)
            return None

        # Verify head and tail
        if data[:2] != cls.HEAD or data[-2:] != cls.TAIL:
            return None

        cmd = data[2]
        data_len = data[3]

        if len(data) != 7 + data_len:
            return None

        payload = data[4:4 + data_len]
        checksum = data[4 + data_len]

        # Verify checksum
        calculated = 0
        for b in data[2:4 + data_len]:
            calculated ^= b

        if calculated != checksum:
            return None

        return cls(command=cmd, data=payload)

    def __repr__(self) -> str:
        return f"Packet(cmd=0x{self.command:02X}, data={self.data.hex()})"


class CatPrinterPacket:
    """
    Cat Printer style packet format (alternative protocol).

    Structure:
        Magic0:     0x51
        Magic1:     0x78
        CommandID:  0x00-0xFF
        AlwaysZero: 0x00
        DataSize:   0x00-0xFF
        AlwaysZero: 0x00
        Data:       [bytes]
        DataCRC8:   CRC8 checksum
        Magic4:     0xFF
    """

    # CRC8 lookup table
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

    @classmethod
    def crc8(cls, data: bytes) -> int:
        """Calculate CRC8 checksum."""
        crc = 0
        for byte in data:
            crc = cls.CRC8_TABLE[(crc ^ byte) & 0xFF]
        return crc

    @classmethod
    def encode(cls, cmd: int, data: bytes = b"") -> bytes:
        """Encode a Cat Printer style packet."""
        packet = bytes([0x51, 0x78, cmd, 0x00, len(data), 0x00]) + data
        return packet + bytes([cls.crc8(data), 0xFF])


class ESCPOSPacket:
    """
    ESC/POS style commands (Phomemo D30 compatible).

    Uses standard ESC/POS raster graphics commands with vendor prefix.
    """

    # Vendor prefix used by Phomemo
    VENDOR_PREFIX = bytes.fromhex("1f1124")

    # Standard ESC/POS commands
    ESC = 0x1B
    GS = 0x1D

    @classmethod
    def init(cls) -> bytes:
        """Initialize printer."""
        return cls.VENDOR_PREFIX + bytes([0x00, cls.ESC, 0x40])  # ESC @

    @classmethod
    def raster_image(cls, width_bytes: int, height: int) -> bytes:
        """
        Start raster image mode.

        GS v 0 mode width_lo width_hi height_lo height_hi
        """
        return bytes([
            cls.GS, 0x76, 0x30, 0x00,  # GS v 0 mode
            width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
            height & 0xFF, (height >> 8) & 0xFF,
        ])
