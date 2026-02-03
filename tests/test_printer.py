"""Tests for printer error handling."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from p31sprinter.printer import (
    P31SPrinter,
    PrinterError,
    ConnectionError,
    PrintError,
    ImageError,
    quick_print,
)


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_connection_error_is_printer_error(self):
        """ConnectionError should inherit from PrinterError."""
        err = ConnectionError("test")
        assert isinstance(err, PrinterError)

    def test_print_error_is_printer_error(self):
        """PrintError should inherit from PrinterError."""
        err = PrintError("test")
        assert isinstance(err, PrinterError)

    def test_image_error_is_printer_error(self):
        """ImageError should inherit from PrinterError."""
        err = ImageError("test")
        assert isinstance(err, PrinterError)


class TestLoadImage:
    """Test image loading functionality."""

    def test_load_pil_image(self):
        """Test loading a PIL Image object."""
        printer = P31SPrinter()
        img = Image.new("1", (10, 10), color=1)
        result = printer._load_image(img)
        assert result.mode == "1"
        assert result.size == (10, 10)

    def test_load_rgb_image_converts_to_1bit(self):
        """Test that RGB images are converted to 1-bit."""
        printer = P31SPrinter()
        img = Image.new("RGB", (10, 10), color=(255, 255, 255))
        result = printer._load_image(img)
        assert result.mode == "1"

    def test_load_nonexistent_file_raises_image_error(self):
        """Test that loading nonexistent file raises ImageError."""
        printer = P31SPrinter()
        with pytest.raises(ImageError, match="not found"):
            printer._load_image("/nonexistent/path/image.png")

    def test_load_invalid_type_raises_image_error(self):
        """Test that loading invalid type raises ImageError."""
        printer = P31SPrinter()
        with pytest.raises(ImageError, match="Unsupported image type"):
            printer._load_image(12345)

    def test_load_bytes(self, tmp_path):
        """Test loading image from bytes."""
        printer = P31SPrinter()
        img = Image.new("1", (10, 10), color=1)
        img_path = tmp_path / "test.png"
        img.save(img_path)
        with open(img_path, "rb") as f:
            img_bytes = f.read()
        result = printer._load_image(img_bytes)
        assert result.mode == "1"

    def test_load_path(self, tmp_path):
        """Test loading image from Path object."""
        printer = P31SPrinter()
        img = Image.new("1", (10, 10), color=1)
        img_path = tmp_path / "test.png"
        img.save(img_path)
        result = printer._load_image(img_path)
        assert result.mode == "1"


class TestPrintImageErrorHandling:
    """Test print_image error handling."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock BLE connection."""
        conn = MagicMock()
        conn.is_connected = True
        conn.get_mtu = AsyncMock(return_value=100)
        conn.write_chunked = AsyncMock(return_value=True)
        return conn

    @pytest.mark.asyncio
    async def test_not_connected_raises_connection_error(self):
        """Test that printing when not connected raises ConnectionError."""
        printer = P31SPrinter()
        printer.connection = MagicMock()
        printer.connection.is_connected = False

        img = Image.new("1", (10, 10), color=1)
        with pytest.raises(ConnectionError, match="Not connected"):
            await printer.print_image(img)

    @pytest.mark.asyncio
    async def test_invalid_image_raises_image_error(self, mock_connection):
        """Test that invalid image raises ImageError."""
        printer = P31SPrinter()
        printer.connection = mock_connection

        with pytest.raises(ImageError, match="not found"):
            await printer.print_image("/nonexistent/image.png")

    @pytest.mark.asyncio
    async def test_write_failure_raises_print_error(self, mock_connection):
        """Test that write failure raises PrintError."""
        mock_connection.write_chunked = AsyncMock(return_value=False)

        printer = P31SPrinter()
        printer.connection = mock_connection

        img = Image.new("1", (10, 10), color=1)
        with pytest.raises(PrintError, match="failed"):
            await printer.print_image(img)

    @pytest.mark.asyncio
    async def test_success_returns_true(self, mock_connection):
        """Test that successful print returns True."""
        printer = P31SPrinter()
        printer.connection = mock_connection

        img = Image.new("1", (10, 10), color=1)
        result = await printer.print_image(img)
        assert result is True

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, mock_connection):
        """Test retry logic on transient failure."""
        # Fail first two times, succeed on third
        mock_connection.write_chunked = AsyncMock(
            side_effect=[False, False, True]
        )

        printer = P31SPrinter()
        printer.connection = mock_connection

        img = Image.new("1", (10, 10), color=1)
        result = await printer.print_image(img, retries=2, retry_delay=0.01)
        assert result is True
        assert mock_connection.write_chunked.call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises_print_error(self, mock_connection):
        """Test that exhausted retries raises PrintError."""
        mock_connection.write_chunked = AsyncMock(return_value=False)

        printer = P31SPrinter()
        printer.connection = mock_connection

        img = Image.new("1", (10, 10), color=1)
        with pytest.raises(PrintError, match="after 3 attempt"):
            await printer.print_image(img, retries=2, retry_delay=0.01)
        assert mock_connection.write_chunked.call_count == 3

    @pytest.mark.asyncio
    async def test_connection_lost_during_retry_raises_connection_error(
        self, mock_connection
    ):
        """Test that connection lost during retry raises ConnectionError."""
        mock_connection.write_chunked = AsyncMock(return_value=False)

        printer = P31SPrinter()
        printer.connection = mock_connection

        # Simulate connection lost after first attempt
        call_count = [0]

        def check_connected():
            call_count[0] += 1
            return call_count[0] < 2  # Connected on first call, disconnected after

        type(mock_connection).is_connected = property(lambda self: check_connected())

        img = Image.new("1", (10, 10), color=1)
        with pytest.raises(ConnectionError, match="lost"):
            await printer.print_image(img, retries=2, retry_delay=0.01)


class TestConnectRetry:
    """Test connection retry logic."""

    @pytest.mark.asyncio
    async def test_connect_success_returns_true(self):
        """Test successful connection returns True."""
        printer = P31SPrinter()
        printer.connection = MagicMock()
        printer.connection.connect = AsyncMock(return_value=True)
        printer.connection.write = AsyncMock(return_value=True)
        printer.connection.read_response = AsyncMock(return_value=None)

        result = await printer.connect("AA:BB:CC:DD:EE:FF")
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_failure_returns_false(self):
        """Test connection failure returns False."""
        printer = P31SPrinter()
        printer.connection = MagicMock()
        printer.connection.connect = AsyncMock(return_value=False)

        result = await printer.connect("AA:BB:CC:DD:EE:FF")
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_retry_on_failure(self):
        """Test retry logic on connection failure."""
        printer = P31SPrinter()
        printer.connection = MagicMock()
        printer.connection.connect = AsyncMock(
            side_effect=[False, False, True]
        )
        printer.connection.write = AsyncMock(return_value=True)
        printer.connection.read_response = AsyncMock(return_value=None)

        result = await printer.connect(
            "AA:BB:CC:DD:EE:FF", retries=2, retry_delay=0.01
        )
        assert result is True
        assert printer.connection.connect.call_count == 3


class TestQuickPrint:
    """Test quick_print convenience function."""

    @pytest.mark.asyncio
    async def test_connection_failure_raises(self):
        """Test that connection failure raises ConnectionError."""
        with patch.object(P31SPrinter, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = False
            with patch.object(
                P31SPrinter, "disconnect", new_callable=AsyncMock
            ):
                with pytest.raises(ConnectionError):
                    await quick_print("AA:BB:CC:DD:EE:FF", "/some/image.png")
