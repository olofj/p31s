"""
P31S Printer Command Definitions.

This module provides high-level command builders for the P31S printer.
Commands are built using the protocol module's packet format.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from .protocol import Packet, PacketType


class LabelType(IntEnum):
    """Label type identifiers."""
    GAP = 1      # Labels with gaps between them
    BLACK_MARK = 2  # Labels with black marks
    CONTINUOUS = 3  # Continuous tape


class PrintDensity(IntEnum):
    """Print density levels."""
    LIGHT = 1
    NORMAL = 2
    DARK = 3


@dataclass
class PrinterStatus:
    """Parsed printer status response."""
    paper_present: bool = True
    cover_open: bool = False
    battery_low: bool = False
    printing: bool = False
    error: bool = False
    raw_data: bytes = b""

    @classmethod
    def from_response(cls, data: bytes) -> "PrinterStatus":
        """Parse status from response bytes."""
        status = cls(raw_data=data)

        # Status byte parsing will be determined during protocol RE
        # This is a placeholder structure
        if len(data) > 0:
            status_byte = data[0] if isinstance(data[0], int) else ord(data[0])
            status.paper_present = not bool(status_byte & 0x01)
            status.cover_open = bool(status_byte & 0x02)
            status.battery_low = bool(status_byte & 0x04)
            status.printing = bool(status_byte & 0x08)
            status.error = bool(status_byte & 0x80)

        return status


class Commands:
    """Command builders for P31S printer."""

    @staticmethod
    def connect() -> bytes:
        """Build connection/handshake command."""
        return Packet(PacketType.CONNECT, b"\x01").encode()

    @staticmethod
    def heartbeat() -> bytes:
        """Build heartbeat/keep-alive command."""
        return Packet(PacketType.HEARTBEAT, b"\x01").encode()

    @staticmethod
    def get_info() -> bytes:
        """Request printer information."""
        return Packet(PacketType.GET_INFO, b"").encode()

    @staticmethod
    def set_label_type(label_type: LabelType) -> bytes:
        """Set the label type (gap, black mark, continuous)."""
        return Packet(PacketType.SET_LABEL_TYPE, bytes([label_type])).encode()

    @staticmethod
    def set_density(density: PrintDensity) -> bytes:
        """Set print density."""
        return Packet(PacketType.SET_LABEL_DENSITY, bytes([density])).encode()

    @staticmethod
    def set_page_size(width: int, height: int) -> bytes:
        """
        Set page/label size in pixels.

        Args:
            width: Label width in pixels (e.g., 96 for 12mm at 203 DPI)
            height: Label height in pixels
        """
        # Pack as little-endian 16-bit values
        data = bytes([
            width & 0xFF, (width >> 8) & 0xFF,
            height & 0xFF, (height >> 8) & 0xFF,
        ])
        return Packet(PacketType.SET_PAGE_SIZE, data).encode()

    @staticmethod
    def print_start() -> bytes:
        """Start a print job."""
        return Packet(PacketType.PRINT_START, b"\x01").encode()

    @staticmethod
    def print_end() -> bytes:
        """End a print job."""
        return Packet(PacketType.PRINT_END, b"\x01").encode()

    @staticmethod
    def page_end() -> bytes:
        """Signal end of current page/label."""
        return Packet(PacketType.PAGE_END, b"\x01").encode()

    @staticmethod
    def print_bitmap_row(row_data: bytes) -> bytes:
        """
        Send a single row of bitmap data.

        Args:
            row_data: Row pixels as bytes (1 bit per pixel, MSB first)
        """
        return Packet(PacketType.PRINT_BITMAP_ROW, row_data).encode()

    @staticmethod
    def print_empty_rows(count: int) -> bytes:
        """
        Print multiple empty (white) rows.

        Args:
            count: Number of empty rows to print
        """
        # Pack count as 16-bit little-endian
        data = bytes([count & 0xFF, (count >> 8) & 0xFF])
        return Packet(PacketType.PRINT_EMPTY_ROWS, data).encode()

    @staticmethod
    def print_bitmap_row_indexed(row_index: int, row_data: bytes) -> bytes:
        """
        Send a bitmap row with explicit index.

        Args:
            row_index: Row number (0-based)
            row_data: Row pixels as bytes
        """
        data = bytes([row_index & 0xFF, (row_index >> 8) & 0xFF]) + row_data
        return Packet(PacketType.PRINT_BITMAP_ROW_INDEXED, data).encode()


class ResponseParser:
    """Parse responses from the printer."""

    @staticmethod
    def parse(data: bytes) -> Optional[dict]:
        """
        Parse a response packet.

        Returns a dict with:
            - command: The command this is a response to
            - success: Whether the command succeeded
            - data: Any response data
        """
        packet = Packet.decode(data)
        if not packet:
            return None

        return {
            "command": packet.command,
            "success": len(packet.data) == 0 or packet.data[0] != 0x00,
            "data": packet.data,
        }
