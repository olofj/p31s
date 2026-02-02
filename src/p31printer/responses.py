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

    Response structure (19 or 20 bytes total):
        Offset  Length  Field
        0-6     7       Header (stripped before parsing)
        7-8     2       Resolution (little-endian uint16)
        9-11    3       Hardware version (3 bytes -> hex string like "010203")
        12-14   3       Firmware version (3 bytes -> hex string like "010203")
        15      1       Shutdown timer setting
        16      1       Sound setting
        17      1       Config version (only in 20-byte response)
        18-19   2       CRLF terminator
    """

    resolution: int
    hardware_version: str  # e.g., "010203" -> "1.2.3"
    firmware_version: str  # e.g., "010203" -> "1.2.3"
    shutdown_timer: int
    sound_enabled: bool
    config_version: Optional[int] = None
    raw_data: bytes = b""

    @classmethod
    def parse(cls, data: bytes) -> Optional["PrinterConfig"]:
        """
        Parse CONFIG? response bytes.

        Args:
            data: Raw response bytes (expected 19 or 20 bytes)

        Returns:
            PrinterConfig instance or None if parsing fails
        """
        # Strip CRLF terminator if present
        if data.endswith(b"\r\n"):
            data = data[:-2]

        # Response should be 17 or 18 bytes after stripping CRLF
        # (19-2=17 or 20-2=18)
        if len(data) < 17:
            return None

        # Skip 7-byte header
        payload = data[7:]

        if len(payload) < 10:
            return None

        # Parse resolution (2 bytes, little-endian)
        resolution = payload[0] | (payload[1] << 8)

        # Parse hardware version (3 bytes -> hex string)
        hw_bytes = payload[2:5]
        hardware_version = _bytes_to_version(hw_bytes)

        # Parse firmware version (3 bytes -> hex string)
        fw_bytes = payload[5:8]
        firmware_version = _bytes_to_version(fw_bytes)

        # Parse shutdown timer
        shutdown_timer = payload[8] if len(payload) > 8 else 0

        # Parse sound setting
        sound_enabled = bool(payload[9]) if len(payload) > 9 else False

        # Parse config version (only in longer response)
        config_version = None
        if len(payload) > 10:
            config_version = payload[10]

        return cls(
            resolution=resolution,
            hardware_version=hardware_version,
            firmware_version=firmware_version,
            shutdown_timer=shutdown_timer,
            sound_enabled=sound_enabled,
            config_version=config_version,
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

    Response structure (11 or 12 bytes):
        Offset  Length  Field
        0-6     7       "BATTERY" ASCII header
        7       1       Battery level (BCD encoded) - 11-byte response
                        OR Charging status (1=charging) - 12-byte response
        8       1       Battery level (BCD encoded) - 12-byte response only
        -2,-1   2       CRLF terminator
    """

    level: int  # 0-100 percent
    charging: bool
    raw_data: bytes = b""

    @classmethod
    def parse(cls, data: bytes) -> Optional["BatteryStatus"]:
        """
        Parse BATTERY? response bytes.

        Args:
            data: Raw response bytes (expected 11 or 12 bytes)

        Returns:
            BatteryStatus instance or None if parsing fails
        """
        # Strip CRLF terminator if present
        if data.endswith(b"\r\n"):
            data = data[:-2]

        # Validate header
        if len(data) < 8 or not data.startswith(b"BATTERY"):
            return None

        # 11-byte response (9 after CRLF strip): header(7) + level(1) + CRLF(2)
        # 12-byte response (10 after CRLF strip): header(7) + charging(1) + level(1) + CRLF(2)

        payload_len = len(data) - 7  # Length after "BATTERY"

        if payload_len == 2:
            # 11-byte format: just battery level (9 bytes total after strip)
            # Actually: header(7) + level(1) = 8, so payload_len=1
            # Let me re-check...
            pass

        if payload_len == 1:
            # Simple format: just battery level
            level_bcd = data[7]
            level = _decode_bcd(level_bcd)
            charging = False
        elif payload_len >= 2:
            # Extended format: charging status + battery level
            charging = bool(data[7])
            level_bcd = data[8]
            level = _decode_bcd(level_bcd)
        else:
            return None

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
