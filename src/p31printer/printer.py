"""
High-Level P31S Printer Interface.

Provides a simple API for printing labels on the P31S printer.
"""

import asyncio
from pathlib import Path
from typing import Optional, Union

from PIL import Image

from .commands import Commands, LabelType, PrintDensity, PrinterStatus
from .connection import BLEConnection, PrinterInfo
from .image import ImageProcessor
from .protocol import Packet


class P31Printer:
    """High-level interface to P31S label printer."""

    def __init__(self):
        self.connection = BLEConnection()
        self.image_processor = ImageProcessor()
        self._debug = False

    def set_debug(self, enabled: bool):
        """Enable/disable debug output."""
        self._debug = enabled

    def _log(self, message: str):
        """Print debug message if enabled."""
        if self._debug:
            print(f"[P31] {message}")

    @classmethod
    async def scan(cls, timeout: float = 10.0) -> list[PrinterInfo]:
        """Scan for available P31S printers."""
        return await BLEConnection.scan(timeout)

    async def connect(self, address: str) -> bool:
        """
        Connect to a printer.

        Args:
            address: Bluetooth address of the printer

        Returns:
            True if connection successful
        """
        self._log(f"Connecting to {address}...")
        success = await self.connection.connect(address)

        if success:
            self._log("Connected, sending handshake...")
            # Send initial handshake
            await self.connection.write(Commands.connect())
            response = await self.connection.read_response(timeout=2.0)
            if response:
                self._log(f"Handshake response: {response.hex()}")

        return success

    async def disconnect(self):
        """Disconnect from the printer."""
        await self.connection.disconnect()
        self._log("Disconnected")

    async def get_status(self) -> Optional[PrinterStatus]:
        """Query printer status."""
        await self.connection.write(Commands.get_info())
        response = await self.connection.read_response(timeout=2.0)

        if response:
            return PrinterStatus.from_response(response)
        return None

    async def feed(self, lines: int = 20):
        """Feed paper forward."""
        # This may need adjustment based on actual protocol
        self._log(f"Feeding {lines} lines...")
        # Some printers use empty rows for feeding
        await self.connection.write(Commands.print_empty_rows(lines))

    async def print_image(
        self,
        image: Union[str, Path, bytes, Image.Image],
        density: PrintDensity = PrintDensity.NORMAL,
        label_type: LabelType = LabelType.GAP,
        copies: int = 1,
    ) -> bool:
        """
        Print an image as a label.

        Args:
            image: Image source (path, bytes, or PIL Image)
            density: Print darkness level
            label_type: Type of label media
            copies: Number of copies to print

        Returns:
            True if print job completed successfully
        """
        if not self.connection.is_connected:
            self._log("Not connected!")
            return False

        # Load and prepare image
        self._log("Processing image...")
        img = self.image_processor.load(image)
        img = self.image_processor.prepare(img)

        width = img.width
        height = img.height
        self._log(f"Image size: {width}x{height} pixels")

        # Configure print job
        self._log("Configuring print job...")
        await self.connection.write(Commands.set_label_type(label_type))
        await asyncio.sleep(0.05)

        await self.connection.write(Commands.set_density(density))
        await asyncio.sleep(0.05)

        await self.connection.write(Commands.set_page_size(width, height))
        await asyncio.sleep(0.05)

        for copy in range(copies):
            if copies > 1:
                self._log(f"Printing copy {copy + 1}/{copies}...")

            # Start print job
            await self.connection.write(Commands.print_start())
            await asyncio.sleep(0.1)

            # Send image data row by row
            rows = list(self.image_processor.iter_rows(img))
            compressed = self.image_processor.count_empty_rows(rows)

            self._log(f"Sending {len(rows)} rows ({len(compressed)} packets)...")

            for item in compressed:
                if item[0] == "empty":
                    await self.connection.write(Commands.print_empty_rows(item[1]))
                else:
                    await self.connection.write(Commands.print_bitmap_row(item[1]))

                # Small delay to avoid overwhelming the printer
                await asyncio.sleep(0.001)

            # End page/job
            await self.connection.write(Commands.page_end())
            await asyncio.sleep(0.05)

            await self.connection.write(Commands.print_end())
            await asyncio.sleep(0.1)

        self._log("Print job complete")
        return True

    async def print_test_pattern(self) -> bool:
        """Print a simple test pattern."""
        from .image import create_test_pattern

        self._log("Creating test pattern...")
        pattern = create_test_pattern()
        return await self.print_image(pattern)

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
        self._log(f"TX: {data.hex()}")
        await self.connection.write(data)
        response = await self.connection.read_response(timeout=2.0)
        if response:
            self._log(f"RX: {response.hex()}")
        return response

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to a printer."""
        return self.connection.is_connected


async def quick_print(address: str, image_path: str) -> bool:
    """
    Convenience function to quickly print an image.

    Args:
        address: Printer Bluetooth address
        image_path: Path to image file

    Returns:
        True if successful
    """
    printer = P31Printer()

    try:
        if await printer.connect(address):
            return await printer.print_image(image_path)
        return False
    finally:
        await printer.disconnect()
