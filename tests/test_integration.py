"""
Integration tests for P31S printer.

These tests require real hardware to run. By default, tests marked with @pytest.mark.hardware
are skipped. To run them, use:

    pytest tests/ -m hardware --address=XX:XX:XX:XX:XX:XX

Where XX:XX:XX:XX:XX:XX is the Bluetooth address of your P31S printer.
"""

import asyncio

import pytest
from PIL import Image

from p31sprinter import P31SPrinter
from p31sprinter.connection import PrinterInfo


# Fixtures (printer_address, connected_printer) are defined in conftest.py


# --- Connection Tests ---


class TestConnection:
    """Tests for printer connection functionality."""

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_scan_finds_printers(self):
        """Test that scan can find P31S printers."""
        printers = await P31SPrinter.scan(timeout=5.0)

        # This test passes if scan completes without error
        # Whether printers are found depends on hardware availability
        assert isinstance(printers, list)
        for printer in printers:
            assert isinstance(printer, PrinterInfo)
            assert printer.name
            assert printer.address

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_connect_disconnect(self, printer_address):
        """Test connecting and disconnecting from printer."""
        printer = P31SPrinter()

        # Connect
        connected = await printer.connect(printer_address)
        assert connected is True
        assert printer.is_connected is True

        # Disconnect
        await printer.disconnect()
        assert printer.is_connected is False

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_reconnect_after_disconnect(self, printer_address):
        """Test reconnecting after a disconnect."""
        printer = P31SPrinter()

        # First connection
        connected = await printer.connect(printer_address)
        assert connected is True
        await printer.disconnect()

        # Wait a moment before reconnecting
        await asyncio.sleep(1.0)

        # Second connection
        connected = await printer.connect(printer_address)
        assert connected is True
        await printer.disconnect()


# --- Discovery Tests ---


class TestDiscovery:
    """Tests for GATT service discovery."""

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_gatt_service_discovery(self, connected_printer):
        """Test that we can discover GATT services."""
        services = await connected_printer.discover_services()

        assert len(services) > 0
        for service in services:
            assert service.service_uuid
            assert isinstance(service.characteristics, list)

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_characteristic_properties(self, connected_printer):
        """Test that discovered characteristics have expected properties."""
        services = await connected_printer.discover_services()

        has_write = False
        has_notify = False

        for service in services:
            for char in service.characteristics:
                props = char.get("properties", [])
                if "write" in props or "write-without-response" in props:
                    has_write = True
                if "notify" in props or "indicate" in props:
                    has_notify = True

        assert has_write, "No writable characteristic found"
        assert has_notify, "No notify characteristic found"


# --- Status Tests ---


class TestStatus:
    """Tests for printer status queries."""

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_get_config(self, connected_printer):
        """Test querying printer configuration."""
        config = await connected_printer.get_config()

        # Config may be None if printer doesn't respond to CONFIG?
        # but should not raise an exception
        if config is not None:
            assert config.firmware_version
            assert config.resolution > 0

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_get_battery(self, connected_printer):
        """Test querying battery status."""
        battery = await connected_printer.get_battery()

        # Battery may be None if printer doesn't respond to BATTERY?
        # but should not raise an exception
        if battery is not None:
            assert 0 <= battery.level <= 100


# --- Print Tests ---


class TestPrint:
    """Tests for print functionality.

    WARNING: These tests will actually print labels!
    Only run if you have paper loaded and are ready to print.
    """

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_print_simple_image(self, connected_printer, tmp_path):
        """Test printing a simple black square."""
        # Create a simple test image
        img = Image.new("1", (50, 50), color=1)  # White background
        for y in range(10, 40):
            for x in range(10, 40):
                img.putpixel((x, y), 0)  # Black square

        img_path = tmp_path / "test_square.png"
        img.save(img_path)

        result = await connected_printer.print_image(str(img_path))
        assert result is True

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_print_with_density_settings(self, connected_printer, tmp_path):
        """Test printing with different density settings."""
        from p31sprinter.tspl import Density

        # Create a test pattern
        img = Image.new("1", (60, 60), color=1)
        for y in range(0, 60, 2):
            for x in range(60):
                img.putpixel((x, y), 0)  # Horizontal stripes

        img_path = tmp_path / "test_stripes.png"
        img.save(img_path)

        # Print with medium density
        result = await connected_printer.print_image(
            str(img_path),
            density=Density.LEVEL_8,
        )
        assert result is True

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_print_multiple_copies(self, connected_printer, tmp_path):
        """Test printing multiple copies."""
        # Create a small test image
        img = Image.new("1", (30, 30), color=1)
        for y in range(5, 25):
            for x in range(5, 25):
                if (x + y) % 2 == 0:
                    img.putpixel((x, y), 0)  # Checkerboard

        img_path = tmp_path / "test_checker.png"
        img.save(img_path)

        # Print 2 copies
        result = await connected_printer.print_image(
            str(img_path),
            copies=2,
        )
        assert result is True

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_print_test_pattern(self, connected_printer):
        """Test the built-in test pattern printing."""
        result = await connected_printer.print_test_pattern()
        assert result is True

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_feed_label(self, connected_printer):
        """Test feeding a blank label."""
        # Feed should complete without error
        await connected_printer.feed()
        # No assertion needed - if it doesn't raise, it passed


# --- Error Handling Tests ---


class TestErrorHandling:
    """Tests for error handling with real hardware."""

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_connect_invalid_address_fails(self):
        """Test that connecting to invalid address fails gracefully."""
        printer = P31SPrinter()

        # Use an invalid but properly formatted address
        result = await printer.connect("00:00:00:00:00:00", retries=0)
        assert result is False

    @pytest.mark.hardware
    @pytest.mark.asyncio
    async def test_print_after_disconnect_raises(self, printer_address):
        """Test that printing after disconnect raises appropriate error."""
        from p31sprinter.printer import ConnectionError

        printer = P31SPrinter()
        await printer.connect(printer_address)
        await printer.disconnect()

        img = Image.new("1", (10, 10), color=1)

        with pytest.raises(ConnectionError):
            await printer.print_image(img)
