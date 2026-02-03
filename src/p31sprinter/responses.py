"""
Response Parsers for P31S Printer Status Commands.

This module parses responses from the text-based status commands
(CONFIG?, BATTERY?, etc.) as documented in PrinterConfig.java
from the decompiled Labelnize APK.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PrinterConfig:
    """
    Parsed CONFIG? response.

    Actual response structure (19 bytes, verified from hardware):
        Offset  Length  Field
        0-6     7       Header "CONFIG " (including trailing space)
        7       1       Padding (0x00)
        8       1       Resolution (single byte, e.g., 203 for 203 DPI)
        9       1       Padding (0x00)
        10-12   3       Hardware version (3 bytes -> "0.1.0")
        13-15   3       Firmware version (3 bytes -> "1.4.2")
        16      1       Settings byte (shutdown/sound)
        17-18   2       CRLF terminator
    """

    resolution: int
    hardware_version: str  # e.g., "000100" -> "0.1.0"
    firmware_version: str  # e.g., "010402" -> "1.4.2"
    shutdown_timer: int
    sound_enabled: bool
    config_version: Optional[int] = None
    raw_data: bytes = b""

    @classmethod
    def parse(cls, data: bytes) -> Optional["PrinterConfig"]:
        """
        Parse CONFIG? response bytes.

        Args:
            data: Raw response bytes (expected 19 bytes)

        Returns:
            PrinterConfig instance or None if parsing fails
        """
        # Strip CRLF terminator if present
        if data.endswith(b"\r\n"):
            data = data[:-2]

        # Verify header starts with "CONFIG"
        if not data.startswith(b"CONFIG"):
            return None

        # Response should be 17 bytes after stripping CRLF
        if len(data) < 17:
            return None

        # Skip 7-byte header "CONFIG "
        payload = data[7:]

        if len(payload) < 10:
            return None

        # Parse resolution (single byte at offset 1, after padding byte)
        # payload[0] = padding (0x00)
        # payload[1] = resolution (e.g., 203)
        # payload[2] = padding (0x00)
        resolution = payload[1]

        # Parse hardware version (3 bytes at offset 3)
        hw_bytes = payload[3:6]
        hardware_version = _bytes_to_version(hw_bytes)

        # Parse firmware version (3 bytes at offset 6)
        fw_bytes = payload[6:9]
        firmware_version = _bytes_to_version(fw_bytes)

        # Parse settings byte at offset 9
        settings = payload[9] if len(payload) > 9 else 0
        shutdown_timer = settings  # May need further decoding
        sound_enabled = False  # May be encoded in settings byte

        return cls(
            resolution=resolution,
            hardware_version=hardware_version,
            firmware_version=firmware_version,
            shutdown_timer=shutdown_timer,
            sound_enabled=sound_enabled,
            config_version=None,
            raw_data=data,
        )

    def firmware_version_display(self) -> str:
        """Return firmware version in displayable format (e.g., '1.2.3')."""
        return _hex_version_to_display(self.firmware_version)

    def hardware_version_display(self) -> str:
        """Return hardware version in displayable format (e.g., '1.2.3')."""
        return _hex_version_to_display(self.hardware_version)

    def __str__(self) -> str:
        return (
            f"PrinterConfig(\n"
            f"  resolution={self.resolution} DPI,\n"
            f"  hardware_version={self.hardware_version_display()},\n"
            f"  firmware_version={self.firmware_version_display()},\n"
            f"  shutdown_timer={self.shutdown_timer},\n"
            f"  sound_enabled={self.sound_enabled},\n"
            f"  config_version={self.config_version}\n"
            f")"
        )


@dataclass
class BatteryStatus:
    """
    Parsed BATTERY? response.

    Actual response structure (12 bytes, verified from hardware):
        Offset  Length  Field
        0-7     8       "BATTERY " ASCII header (including trailing space)
        8       1       Battery level (BCD encoded, e.g., 0x75 = 75%)
        9       1       Charging status (0=not charging, 1=charging)
        10-11   2       CRLF terminator
    """

    level: int  # 0-100 percent
    charging: bool
    raw_data: bytes = b""

    @classmethod
    def parse(cls, data: bytes) -> Optional["BatteryStatus"]:
        """
        Parse BATTERY? response bytes.

        Args:
            data: Raw response bytes (expected 12 bytes)

        Returns:
            BatteryStatus instance or None if parsing fails
        """
        # Strip CRLF terminator if present
        if data.endswith(b"\r\n"):
            data = data[:-2]

        # Validate header - note it's "BATTERY " with trailing space (8 bytes)
        if len(data) < 10 or not data.startswith(b"BATTERY"):
            return None

        # Header is 8 bytes "BATTERY " (with space)
        # Byte 8: battery level (BCD)
        # Byte 9: charging status
        level_bcd = data[8]
        level = _decode_bcd(level_bcd)
        charging = bool(data[9])

        return cls(
            level=level,
            charging=charging,
            raw_data=data,
        )

    def __str__(self) -> str:
        charging_str = " (charging)" if self.charging else ""
        return f"Battery: {self.level}%{charging_str}"


@dataclass
class ChunkSize:
    """Parsed GETCHUNKSIZE response."""

    size: int
    raw_data: bytes = b""

    @classmethod
    def parse(cls, data: bytes) -> Optional["ChunkSize"]:
        """Parse GETCHUNKSIZE response."""
        # Strip CRLF
        if data.endswith(b"\r\n"):
            data = data[:-2]

        # Try to parse as integer
        try:
            # Response may be just a number, or prefixed
            text = data.decode("ascii").strip()
            # Try to extract number from response
            import re

            match = re.search(r"\d+", text)
            if match:
                return cls(size=int(match.group()), raw_data=data)
        except (ValueError, UnicodeDecodeError):
            pass

        return None


@dataclass
class PrintedCount:
    """Parsed GETPRINTEDCOUNT response."""

    count: int
    raw_data: bytes = b""

    @classmethod
    def parse(cls, data: bytes) -> Optional["PrintedCount"]:
        """Parse GETPRINTEDCOUNT response."""
        # Strip CRLF
        if data.endswith(b"\r\n"):
            data = data[:-2]

        try:
            text = data.decode("ascii").strip()
            import re

            match = re.search(r"\d+", text)
            if match:
                return cls(count=int(match.group()), raw_data=data)
        except (ValueError, UnicodeDecodeError):
            pass

        return None


def _bytes_to_version(data: bytes) -> str:
    """Convert 3 bytes to hex version string (e.g., '010203')."""
    return "".join(f"{b:02x}" for b in data)


def _hex_version_to_display(hex_version: str) -> str:
    """Convert hex version string to display format (e.g., '010203' -> '1.2.3')."""
    if len(hex_version) == 6:
        major = int(hex_version[0:2], 16)
        minor = int(hex_version[2:4], 16)
        patch = int(hex_version[4:6], 16)
        return f"{major}.{minor}.{patch}"
    return hex_version


def _decode_bcd(value: int) -> int:
    """
    Decode BCD (Binary-Coded Decimal) to integer.

    BCD encodes each decimal digit in 4 bits.
    For example: 0x99 = 99 decimal, 0x50 = 50 decimal
    """
    high = (value >> 4) & 0x0F
    low = value & 0x0F
    return high * 10 + low
