"""
High-Level P31S Printer Interface.

Provides a simple API for printing labels on the P31S printer.
Uses TSPL text-based commands (verified working via iOS capture analysis).
"""

import asyncio
from pathlib import Path
from typing import Optional, Union

from PIL import Image

from .connection import BLEConnection, PrinterInfo
from .tspl import TSPLCommand, LabelSize, Density, BitmapMode
from .tspl_commands import TSPLCommands
from .responses import PrinterConfig, BatteryStatus


# --- Exception Classes ---


class PrinterError(Exception):
    """Base exception for all printer errors."""

    pass


class ConnectionError(PrinterError):
    """Error connecting to or communicating with printer."""

    pass


class PrintError(PrinterError):
    """Error during print operation."""

    pass


class PaperError(PrinterError):
    """Paper-related error (jam, out of paper, etc.)."""

    pass


class ImageError(PrinterError):
    """Error processing image for printing."""

    pass


class P31SPrinter:
    """
    High-level interface to P31S label printer.

    Uses TSPL text-based commands verified via iOS app capture analysis.
    """

    # Maximum printable resolution (verified via edge testing)
    MAX_WIDTH_PX = 120   # ~15mm at 203 DPI (covers 14mm label width)
    MAX_HEIGHT_PX = 320  # 40mm label height at 203 DPI

    # Optimal padding for centering on 14mm label
    # Content area: 116px (pad_left=4, pad_right=0)
    PAD_LEFT = 4
    PAD_RIGHT = 0

    # Default label size for 40x14mm labels (can be overridden)
    # TSPL orientation: width = print head direction, height = feed direction
    # For 40x14mm physical labels: width=14mm, height=40mm in TSPL terms
    DEFAULT_LABEL_WIDTH_MM = 14.0
    DEFAULT_LABEL_HEIGHT_MM = 40.0
    DEFAULT_GAP_MM = 2.0

    def __init__(self, label_width_mm: float = DEFAULT_LABEL_WIDTH_MM,
                 label_height_mm: float = DEFAULT_LABEL_HEIGHT_MM,
                 gap_mm: float = DEFAULT_GAP_MM):
        """
        Initialize printer interface.

        Args:
            label_width_mm: Label width in millimeters (default 40mm)
            label_height_mm: Label height in millimeters (default 10mm)
            gap_mm: Gap between labels in millimeters (default 2mm)
        """
        self.connection = BLEConnection()
        self.label_size = LabelSize(label_width_mm, label_height_mm, gap_mm)
        self._debug = False

    def set_debug(self, enabled: bool):
        """Enable/disable debug output."""
        self._debug = enabled

    def set_label_size(self, width_mm: float, height_mm: float, gap_mm: float = 2.0):
        """Set label dimensions."""
        self.label_size = LabelSize(width_mm, height_mm, gap_mm)

    def _log(self, message: str):
        """Print debug message if enabled."""
        if self._debug:
            print(f"[P31S] {message}")

    @classmethod
    async def scan(cls, timeout: float = 10.0) -> list[PrinterInfo]:
        """Scan for available P31S printers."""
        return await BLEConnection.scan(timeout)

    async def connect(self, address: str, retries: int = 0, retry_delay: float = 1.0) -> bool:
        """
        Connect to a printer.

        Args:
            address: Bluetooth address of the printer
            retries: Number of connection retries (default 0)
            retry_delay: Delay between retries in seconds (default 1.0)

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails after all retries
        """
        last_error: Optional[Exception] = None
        attempts = retries + 1

        for attempt in range(attempts):
            if attempt > 0:
                self._log(f"Connection retry {attempt}/{retries}...")
                await asyncio.sleep(retry_delay)

            self._log(f"Connecting to {address}...")

            try:
                success = await self.connection.connect(address)

                if success:
                    self._log("Connected, verifying with CONFIG?...")
                    # Verify connection with CONFIG? command
                    await self.connection.write(TSPLCommands.config_query())
                    response = await self.connection.read_response(timeout=2.0)
                    if response:
                        config = PrinterConfig.parse(response)
                        if config:
                            self._log(f"Printer: FW {config.firmware_version}, {config.resolution} DPI")
                    return True
                else:
                    last_error = ConnectionError(f"Failed to connect to {address}")
                    self._log(f"Connection failed (attempt {attempt + 1}/{attempts})")

            except Exception as e:
                last_error = e
                self._log(f"Connection error (attempt {attempt + 1}/{attempts}): {e}")

        # All retries exhausted - raise if caller wants exceptions, otherwise return False
        # For backwards compatibility, return False rather than raising
        return False

    async def disconnect(self):
        """Disconnect from the printer."""
        await self.connection.disconnect()
        self._log("Disconnected")

    async def get_config(self) -> Optional[PrinterConfig]:
        """Query printer configuration."""
        await self.connection.write(TSPLCommands.config_query())
        response = await self.connection.read_response(timeout=2.0)
        if response:
            return PrinterConfig.parse(response)
        return None

    async def get_battery(self) -> Optional[BatteryStatus]:
        """Query battery status."""
        await self.connection.write(TSPLCommands.battery_query())
        response = await self.connection.read_response(timeout=2.0)
        if response:
            return BatteryStatus.parse(response)
        return None

    async def feed(self):
        """Feed one label forward."""
        self._log("Feeding label...")
        cmd = TSPLCommand()
        cmd.formfeed()
        await self.connection.write(cmd.get_commands())

    def _load_image(self, image: Union[str, Path, bytes, Image.Image]) -> Image.Image:
        """
        Load and validate an image for printing.

        Args:
            image: Image source (path, bytes, or PIL Image)

        Returns:
            PIL Image object

        Raises:
            ImageError: If image cannot be loaded or is invalid
        """
        try:
            if isinstance(image, (str, Path)):
                path = Path(image)
                if not path.exists():
                    raise ImageError(f"Image file not found: {path}")
                img = Image.open(path)
            elif isinstance(image, bytes):
                from io import BytesIO
                img = Image.open(BytesIO(image))
            elif isinstance(image, Image.Image):
                img = image
            else:
                raise ImageError(f"Unsupported image type: {type(image)}")

            # Convert to 1-bit if needed
            if img.mode != "1":
                img = img.convert("L").point(lambda x: 0 if x < 128 else 255, mode="1")

            return img
        except ImageError:
            raise
        except Exception as e:
            raise ImageError(f"Failed to load image: {e}") from e

    async def print_image(
        self,
        image: Union[str, Path, bytes, Image.Image],
        density: Density = Density.LEVEL_8,
        x: int = 0,
        y: int = 0,
        copies: int = 1,
        retries: int = 0,
        retry_delay: float = 1.0,
    ) -> bool:
        """
        Print an image as a label using TSPL commands.

        Args:
            image: Image source (path, bytes, or PIL Image)
            density: Print darkness level (0-15, default 8)
            x, y: Position offset in dots (default 0,0)
            copies: Number of copies to print
            retries: Number of retries for transient failures (default 0)
            retry_delay: Delay between retries in seconds (default 1.0)

        Returns:
            True if print job completed successfully

        Raises:
            ConnectionError: If not connected or connection lost
            ImageError: If image cannot be loaded
            PrintError: If print job fails after all retries
        """
        if not self.connection.is_connected:
            raise ConnectionError("Not connected to printer")

        # Load image (may raise ImageError)
        self._log("Loading image...")
        img = self._load_image(image)
        self._log(f"Image size: {img.width}x{img.height} pixels")

        # Build TSPL print job
        self._log("Building TSPL print job...")
        cmd = TSPLCommand()
        cmd.setup_label(self.label_size, density)
        cmd.bitmap_from_image(x, y, img, mode=BitmapMode.OR, dither_black=True)
        cmd.print_label(1, copies)

        job_data = cmd.get_commands()
        self._log(f"Print job size: {len(job_data)} bytes")

        # Send with retry logic
        last_error: Optional[Exception] = None
        attempts = retries + 1

        for attempt in range(attempts):
            if attempt > 0:
                self._log(f"Retry {attempt}/{retries}...")
                await asyncio.sleep(retry_delay)

                # Check if still connected
                if not self.connection.is_connected:
                    raise ConnectionError("Connection lost during print")

            try:
                mtu = await self.connection.get_mtu()
                self._log(f"Sending with chunk size: {mtu} bytes")

                success = await self.connection.write_chunked(job_data, chunk_size=mtu)

                if success:
                    self._log("Print job sent successfully")
                    return True
                else:
                    last_error = PrintError("Write operation failed")
                    self._log(f"Print job failed (attempt {attempt + 1}/{attempts})")

            except Exception as e:
                last_error = e
                self._log(f"Error during print (attempt {attempt + 1}/{attempts}): {e}")

                # Don't retry on connection errors
                if not self.connection.is_connected:
                    raise ConnectionError(f"Connection lost: {e}") from e

        # All retries exhausted
        raise PrintError(
            f"Print failed after {attempts} attempt(s): {last_error}"
        ) from last_error

    async def print_test_pattern(self, retries: int = 0) -> bool:
        """
        Print a simple test pattern (checkerboard).

        Args:
            retries: Number of retries for transient failures (default 0)

        Returns:
            True if print job completed successfully

        Raises:
            ConnectionError: If not connected or connection lost
            PrintError: If print job fails after all retries
        """
        self._log("Creating test pattern...")

        # Create a checkerboard pattern that works with thermal protection
        width = 64
        height = 64
        img = Image.new("1", (width, height), color=1)  # White background

        # Draw checkerboard
        for y in range(height):
            for x in range(width):
                if (x // 8 + y // 8) % 2 == 0:
                    img.putpixel((x, y), 0)  # Black

        return await self.print_image(img, retries=retries)

    async def selftest(self) -> bool:
        """Trigger printer's built-in self-test."""
        self._log("Sending SELFTEST command...")
        await self.connection.write(TSPLCommands.selftest())
        return True

    async def discover_services(self) -> list:
        """
        Discover and return all GATT services.

        Useful for protocol reverse engineering.
        """
        return await self.connection.get_services()

    async def send_raw(self, data: bytes) -> Optional[bytes]:
        """
        Send raw bytes and wait for response.

        Useful for protocol testing.
        """
        self._log(f"TX: {data.hex() if len(data) < 50 else data[:50].hex() + '...'}")
        await self.connection.write(data)
        response = await self.connection.read_response(timeout=2.0)
        if response:
            self._log(f"RX: {response.hex()}")
        return response

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to a printer."""
        return self.connection.is_connected


async def quick_print(
    address: str,
    image_path: str,
    label_width_mm: float = 40.0,
    label_height_mm: float = 14.0,
    retries: int = 0,
) -> bool:
    """
    Convenience function to quickly print an image.

    Args:
        address: Printer Bluetooth address
        image_path: Path to image file
        label_width_mm: Label width in mm (default 40)
        label_height_mm: Label height in mm (default 14)
        retries: Number of retries for transient failures (default 0)

    Returns:
        True if successful

    Raises:
        ConnectionError: If connection fails
        ImageError: If image cannot be loaded
        PrintError: If print job fails after all retries
    """
    printer = P31SPrinter(label_width_mm, label_height_mm)

    try:
        if await printer.connect(address, retries=retries):
            return await printer.print_image(image_path, retries=retries)
        raise ConnectionError(f"Failed to connect to {address}")
    finally:
        await printer.disconnect()
