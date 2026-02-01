"""
TSPL (TSC Printer Language) Protocol Implementation.

TSPL is a text-based command language used by TSC and compatible label printers.
Commands are ASCII strings terminated with CRLF (\\r\\n).

Reference: TSPL/TSPL2 Programming Manual
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from PIL import Image


class Density(IntEnum):
    """Print density levels (0-15)."""
    LEVEL_0 = 0   # Lightest
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5
    LEVEL_6 = 6
    LEVEL_7 = 7   # Medium
    LEVEL_8 = 8   # Default
    LEVEL_9 = 9
    LEVEL_10 = 10
    LEVEL_11 = 11
    LEVEL_12 = 12
    LEVEL_13 = 13
    LEVEL_14 = 14
    LEVEL_15 = 15  # Darkest


class BitmapMode(IntEnum):
    """Bitmap overlay modes."""
    OVERWRITE = 0  # Replace existing content
    OR = 1         # OR with existing content
    XOR = 2        # XOR with existing content
    COMPRESSED = 3  # QuickLZ compressed data


class Direction(IntEnum):
    """Print direction."""
    FORWARD = 0   # Normal
    BACKWARD = 1  # Mirrored


@dataclass
class LabelSize:
    """Label dimensions in millimeters."""
    width: float   # Width in mm
    height: float  # Height in mm
    gap: float = 2.0  # Gap between labels in mm


class TSPLCommand:
    """
    TSPL command builder.

    Builds text-based commands for TSPL-compatible printers.
    All commands are terminated with CRLF.
    """

    CRLF = b"\r\n"

    def __init__(self):
        self._commands: list[bytes] = []

    def clear(self):
        """Clear all queued commands."""
        self._commands.clear()

    def get_commands(self) -> bytes:
        """Get all commands as a single byte string."""
        return b"".join(self._commands)

    def _add(self, cmd: str):
        """Add a command string."""
        self._commands.append(cmd.encode("utf-8") + self.CRLF)

    def _add_raw(self, data: bytes):
        """Add raw bytes."""
        self._commands.append(data)

    # ---- Setup Commands ----

    def size(self, width_mm: float, height_mm: float):
        """Set label size in millimeters."""
        self._add(f"SIZE {width_mm} mm,{height_mm} mm")

    def gap(self, gap_mm: float, offset_mm: float = 0):
        """Set gap between labels."""
        self._add(f"GAP {gap_mm} mm,{offset_mm} mm")

    def bline(self, height_mm: float, offset_mm: float = 0):
        """Set black line mark detection."""
        self._add(f"BLINE {height_mm} mm,{offset_mm} mm")

    def density(self, level: Density):
        """Set print density (0-15)."""
        self._add(f"DENSITY {int(level)}")

    def direction(self, direction: Direction, mirror: int = 0):
        """Set print direction."""
        self._add(f"DIRECTION {int(direction)},{mirror}")

    def reference(self, x: int, y: int):
        """Set reference point for coordinates."""
        self._add(f"REFERENCE {x},{y}")

    def offset(self, distance_mm: float):
        """Set label offset distance."""
        self._add(f"OFFSET {distance_mm} mm")

    def speed(self, speed: float):
        """Set print speed."""
        self._add(f"SPEED {speed}")

    # ---- Buffer Commands ----

    def cls(self):
        """Clear the image buffer."""
        self._add("CLS")

    def home(self):
        """Feed label to home position."""
        self._add("HOME")

    def formfeed(self):
        """Feed one label forward."""
        self._add("FORMFEED")

    def feed(self, dots: int):
        """Feed paper by specified dots."""
        self._add(f"FEED {dots}")

    def backfeed(self, dots: int):
        """Feed paper backward by specified dots."""
        self._add(f"BACKFEED {dots}")

    # ---- Drawing Commands ----

    def bar(self, x: int, y: int, width: int, height: int):
        """Draw a black rectangle."""
        self._add(f"BAR {x},{y},{width},{height}")

    def box(self, x: int, y: int, x_end: int, y_end: int, thickness: int):
        """Draw a rectangle outline."""
        self._add(f"BOX {x},{y},{x_end},{y_end},{thickness}")

    def circle(self, x: int, y: int, diameter: int, thickness: int):
        """Draw a circle."""
        self._add(f"CIRCLE {x},{y},{diameter},{thickness}")

    def erase(self, x: int, y: int, width: int, height: int):
        """Erase (white out) a rectangular area."""
        self._add(f"ERASE {x},{y},{width},{height}")

    def reverse(self, x: int, y: int, width: int, height: int):
        """Reverse (invert) a rectangular area."""
        self._add(f"REVERSE {x},{y},{width},{height}")

    # ---- Text Commands ----

    def text(self, x: int, y: int, font: str, rotation: int,
             x_mul: int, y_mul: int, content: str):
        """
        Draw text.

        Args:
            x, y: Position in dots
            font: Font name (e.g., "1", "2", "TSS24.BF2")
            rotation: 0, 90, 180, or 270 degrees
            x_mul, y_mul: Horizontal and vertical multipliers
            content: Text to print
        """
        self._add(f'TEXT {x},{y},"{font}",{rotation},{x_mul},{y_mul},"{content}"')

    # ---- Barcode Commands ----

    def barcode(self, x: int, y: int, code_type: str, height: int,
                readable: int, rotation: int, narrow: int, wide: int, content: str):
        """
        Draw a 1D barcode.

        Args:
            x, y: Position in dots
            code_type: Barcode type (e.g., "128", "EAN13", "39")
            height: Bar height in dots
            readable: 0=no text, 1=text above, 2=text below
            rotation: 0, 90, 180, or 270 degrees
            narrow, wide: Narrow and wide bar widths
            content: Barcode data
        """
        self._add(f'BARCODE {x},{y},"{code_type}",{height},{readable},{rotation},{narrow},{wide},"{content}"')

    def qrcode(self, x: int, y: int, ecc: str, cell_width: int,
               mode: str, rotation: int, content: str):
        """
        Draw a QR code.

        Args:
            x, y: Position in dots
            ecc: Error correction level (L, M, Q, H)
            cell_width: Cell/module width in dots
            mode: A=auto, M=manual
            rotation: 0, 90, 180, or 270 degrees
            content: QR code data
        """
        self._add(f'QRCODE {x},{y},{ecc},{cell_width},{mode},{rotation},"{content}"')

    # ---- Bitmap Commands ----

    def bitmap(self, x: int, y: int, width_bytes: int, height: int,
               mode: BitmapMode, data: bytes):
        """
        Draw a bitmap image.

        Args:
            x, y: Position in dots
            width_bytes: Width in bytes (8 pixels per byte)
            height: Height in dots
            mode: Overlay mode (0=overwrite, 1=OR, 2=XOR)
            data: Raw bitmap bytes (1 bit per pixel, MSB first)
        """
        cmd = f"BITMAP {x},{y},{width_bytes},{height},{int(mode)},"
        self._add_raw(cmd.encode("utf-8"))
        self._add_raw(data)
        self._add_raw(self.CRLF)

    def bitmap_from_image(self, x: int, y: int, image: Image.Image,
                          mode: BitmapMode = BitmapMode.OVERWRITE):
        """
        Draw a PIL Image as bitmap.

        The image should be 1-bit mode. If not, it will be converted.
        In TSPL, 0 = black (print), 1 = white (no print).
        """
        if image.mode != "1":
            image = image.convert("1")

        width = image.width
        height = image.height
        width_bytes = (width + 7) // 8

        # Convert image to TSPL bitmap format
        # TSPL: 0 = black, 1 = white (opposite of some other formats)
        data = bytearray()

        for y_pos in range(height):
            row_byte = 0
            bit_pos = 7

            for x_pos in range(width):
                pixel = image.getpixel((x_pos, y_pos))
                # PIL 1-bit: 0=black, 255=white
                # TSPL: 0=black (print), 1=white (no print)
                # So we use the pixel value directly (0 stays 0, 255 becomes 1)
                if pixel != 0:
                    row_byte |= (1 << bit_pos)

                bit_pos -= 1
                if bit_pos < 0:
                    data.append(row_byte)
                    row_byte = 0
                    bit_pos = 7

            # Pad last byte if needed
            if bit_pos != 7:
                data.append(row_byte)

            # Ensure row is full width
            while len(data) % width_bytes != 0:
                data.append(0xFF)  # Pad with white

        self.bitmap(x, y, width_bytes, height, mode, bytes(data))

    # ---- Print Commands ----

    def print_label(self, sets: int = 1, copies: int = 1):
        """
        Print labels.

        Args:
            sets: Number of label sets
            copies: Number of copies per set
        """
        self._add(f"PRINT {sets},{copies}")

    # ---- Query Commands ----

    def query_status(self):
        """Query printer status."""
        # Send ESC ! ? sequence
        self._add_raw(bytes([0x1B, 0x21, 0x3F]))

    def selftest(self):
        """Print self-test page."""
        self._add("SELFTEST")

    # ---- Convenience Methods ----

    def setup_label(self, label: LabelSize, density: Density = Density.LEVEL_8):
        """
        Common setup sequence for a label.

        Args:
            label: Label dimensions
            density: Print density
        """
        self.size(label.width, label.height)
        self.gap(label.gap)
        self.density(density)
        self.cls()

    def print_image(self, image: Image.Image, x: int = 0, y: int = 0,
                    copies: int = 1):
        """
        Convenience method to print an image.

        Args:
            image: PIL Image to print
            x, y: Position on label
            copies: Number of copies
        """
        self.bitmap_from_image(x, y, image)
        self.print_label(1, copies)


def create_print_job(label: LabelSize, image: Image.Image,
                     density: Density = Density.LEVEL_8,
                     copies: int = 1) -> bytes:
    """
    Create a complete print job for an image.

    Args:
        label: Label dimensions
        image: Image to print
        density: Print density
        copies: Number of copies

    Returns:
        Complete TSPL command sequence as bytes
    """
    cmd = TSPLCommand()
    cmd.setup_label(label, density)
    cmd.print_image(image, copies=copies)
    return cmd.get_commands()
