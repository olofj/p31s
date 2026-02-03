"""
TSPL Text-Based Commands for P31S Printer.

This module provides text-based commands for printer control and status,
as discovered from the decompiled Labelnize APK.

The P31S uses TSPL (TSC Printer Language) - simple ASCII text commands
terminated with CRLF (\\r\\n).

Command Sources:
- Status commands: O8.java (CONFIG?, BATTERY?, SELFTEST, etc.)
- Print commands: LabelCommand.java (SIZE, GAP, BITMAP, PRINT, etc.)
"""

from enum import IntEnum


class CommandType(IntEnum):
    """Command type identifiers from O8.java."""

    CONFIG = 10
    INITIALIZE = 11
    SELFTEST = 12
    BATTERY = 13
    CHUNK_SIZE = 16
    PRINTED_COUNT = 35


class BitmapMode(IntEnum):
    """Bitmap print modes for BITMAP command."""

    OVERWRITE = 0  # Overwrite existing content
    OR = 1  # OR with existing content
    XOR = 2  # XOR with existing content
    COMPRESSED = 3  # QuickLZ compressed data


class TSPLCommands:
    """
    Text-based status command builders for P31S printer.

    All commands are ASCII strings terminated with CRLF (\\r\\n).
    """

    CRLF = b"\r\n"

    @staticmethod
    def config_query() -> bytes:
        """
        Query printer configuration and firmware version.

        Returns device info including:
        - Resolution
        - Hardware version
        - Firmware version
        - Shutdown timer setting
        - Sound setting

        Response: 19 or 20 bytes (see responses.PrinterConfig.parse)
        """
        return b"CONFIG?" + TSPLCommands.CRLF

    @staticmethod
    def battery_query() -> bytes:
        """
        Query battery status.

        Returns battery level and charging status.

        Response: 11 or 12 bytes (see responses.BatteryStatus.parse)
        """
        return b"BATTERY?" + TSPLCommands.CRLF

    @staticmethod
    def selftest() -> bytes:
        """
        Trigger self-test print.

        Prints a test page with device info and patterns.
        """
        return b"SELFTEST" + TSPLCommands.CRLF

    @staticmethod
    def initialize() -> bytes:
        """
        Initialize the printer.

        Should be called after connecting to reset printer state.
        """
        return b"INITIALPRINTER" + TSPLCommands.CRLF

    @staticmethod
    def get_chunk_size() -> bytes:
        """
        Query the maximum chunk size for data transfers.

        Returns the maximum number of bytes that can be sent
        in a single write operation.
        """
        return b"GETCHUNKSIZE" + TSPLCommands.CRLF

    @staticmethod
    def get_printed_count() -> bytes:
        """
        Query the total print counter.

        Returns the number of labels/pages printed by this device.
        """
        return b"GETPRINTEDCOUNT" + TSPLCommands.CRLF

    # ========== Print Commands (from LabelCommand.java) ==========

    @staticmethod
    def size(width_mm: float, height_mm: float) -> bytes:
        """
        Set label size.

        Args:
            width_mm: Label width in millimeters
            height_mm: Label height in millimeters
        """
        return f"SIZE {width_mm} mm,{height_mm} mm\r\n".encode("ascii")

    @staticmethod
    def gap(gap_mm: float, offset_mm: float = 0) -> bytes:
        """
        Set gap between labels.

        Args:
            gap_mm: Gap height in millimeters
            offset_mm: Offset in millimeters (default 0)
        """
        return f"GAP {gap_mm} mm,{offset_mm} mm\r\n".encode("ascii")

    @staticmethod
    def direction(direction: int = 0, mirror: int = 0) -> bytes:
        """
        Set print direction and mirroring.

        Args:
            direction: 0=normal, 1=reversed (180 degree rotation)
            mirror: 0=no mirror, 1=mirror
        """
        return f"DIRECTION {direction},{mirror}\r\n".encode("ascii")

    @staticmethod
    def density(level: int) -> bytes:
        """
        Set print density/darkness.

        Args:
            level: Density level 0-15 (higher = darker)
        """
        return f"DENSITY {level}\r\n".encode("ascii")

    @staticmethod
    def cls() -> bytes:
        """Clear the image buffer."""
        return b"CLS\r\n"

    @staticmethod
    def print_label(copies: int = 1, sets: int = 1) -> bytes:
        """
        Execute print command.

        Args:
            copies: Number of copies per set
            sets: Number of sets (for serialized data)
        """
        if sets == 1:
            return f"PRINT {copies}\r\n".encode("ascii")
        return f"PRINT {copies},{sets}\r\n".encode("ascii")

    @staticmethod
    def bitmap(x: int, y: int, width_bytes: int, height: int, mode: int, data: bytes) -> bytes:
        """
        Send bitmap image data.

        Args:
            x: X position in dots
            y: Y position in dots
            width_bytes: Width in bytes (pixels / 8)
            height: Height in dots
            mode: BitmapMode value (0=overwrite, 1=OR, 2=XOR, 3=compressed)
            data: Raw binary bitmap data

        Note: Data format is 1-bit per pixel, MSB first.
        For TSPL: 0 = black (burn), 1 = white (no burn)
        Width is rounded up to next byte boundary.
        """
        cmd = f"BITMAP {x},{y},{width_bytes},{height},{mode},".encode("ascii")
        return cmd + data + b"\r\n"

    @staticmethod
    def bar(x: int, y: int, width: int, height: int) -> bytes:
        """
        Draw a filled black rectangle.

        Args:
            x: X position in dots
            y: Y position in dots
            width: Width in dots
            height: Height in dots

        Note: This command may not be supported on all printers.
        The P31S appears to require BITMAP for printing images.
        """
        return f"BAR {x},{y},{width},{height}\r\n".encode("ascii")

    @staticmethod
    def build_print_job(
        width_mm: float,
        height_mm: float,
        gap_mm: float,
        density: int,
        bitmap_data: bytes,
        bitmap_width_bytes: int,
        bitmap_height: int,
        x: int = 0,
        y: int = 0,
        copies: int = 1,
        bitmap_mode: int = BitmapMode.OR,
    ) -> bytes:
        """
        Build a complete print job command sequence.

        This is the standard TSPL sequence used by the Labelnize app
        for P31S printers (command type 0 / isPrintModelAfterSend).

        Args:
            width_mm: Label width in mm
            height_mm: Label height in mm
            gap_mm: Gap between labels in mm
            density: Print density 0-15 (or -1 to skip)
            bitmap_data: Raw bitmap data
            bitmap_width_bytes: Bitmap width in bytes
            bitmap_height: Bitmap height in dots
            x: X offset in dots (default 0)
            y: Y offset in dots (default 0)
            copies: Number of copies (default 1)

        Returns:
            Complete command sequence as bytes
        """
        commands = []
        commands.append(TSPLCommands.size(width_mm, height_mm))
        commands.append(TSPLCommands.gap(gap_mm, 0))
        commands.append(TSPLCommands.direction(0, 0))
        if density >= 0:
            commands.append(TSPLCommands.density(density))
        commands.append(TSPLCommands.cls())
        commands.append(
            TSPLCommands.bitmap(x, y, bitmap_width_bytes, bitmap_height, bitmap_mode, bitmap_data)
        )
        commands.append(TSPLCommands.print_label(copies))
        # Note: Some printers may need FORMFEED to advance to next label
        # Uncomment if label doesn't advance after printing:
        # commands.append(b"FORMFEED\r\n")
        return b"".join(commands)
