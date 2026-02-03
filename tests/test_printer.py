"""Tests for printer error handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from p31s.printer import (
    BLUETOOTH_MAC_PATTERN,
    ConnectionError,
    ImageError,
    P31SPrinter,
    PrinterError,
    PrintError,
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


class TestImageSizeLimits:
    """Test image size validation to prevent memory exhaustion."""

    def test_valid_image_passes(self):
        """Test that normal-sized images pass validation."""
        printer = P31SPrinter()
        img = Image.new("1", (100, 100), color=1)
        result = printer._load_image(img)
        assert result.size == (100, 100)

    def test_max_dimension_passes(self):
        """Test that images at max dimension pass."""
        from p31s.printer import MAX_IMAGE_DIMENSION

        printer = P31SPrinter()
        # Use a thin image to avoid exceeding pixel limit
        img = Image.new("1", (MAX_IMAGE_DIMENSION, 100), color=1)
        result = printer._load_image(img)
        assert result.width == MAX_IMAGE_DIMENSION

    def test_exceeds_max_width_raises_error(self):
        """Test that image exceeding max width raises ImageError."""
        from p31s.printer import MAX_IMAGE_DIMENSION

        printer = P31SPrinter()
        img = Image.new("1", (MAX_IMAGE_DIMENSION + 1, 100), color=1)
        with pytest.raises(ImageError, match="dimensions.*exceed maximum"):
            printer._load_image(img)

    def test_exceeds_max_height_raises_error(self):
        """Test that image exceeding max height raises ImageError."""
        from p31s.printer import MAX_IMAGE_DIMENSION

        printer = P31SPrinter()
        img = Image.new("1", (100, MAX_IMAGE_DIMENSION + 1), color=1)
        with pytest.raises(ImageError, match="dimensions.*exceed maximum"):
            printer._load_image(img)

    def test_max_pixels_passes(self):
        """Test that images at max pixel count pass."""
        from p31s.printer import MAX_IMAGE_PIXELS

        printer = P31SPrinter()
        # sqrt(10_000_000) ≈ 3162
        side = int(MAX_IMAGE_PIXELS**0.5)
        img = Image.new("1", (side, side), color=1)
        result = printer._load_image(img)
        assert result.width * result.height <= MAX_IMAGE_PIXELS

    def test_exceeds_max_pixels_raises_error(self):
        """Test that image exceeding max pixel count raises ImageError."""

        printer = P31SPrinter()
        # Create image just over pixel limit (5000 x 2001 = 10,005,000)
        img = Image.new("1", (5000, 2001), color=1)
        with pytest.raises(ImageError, match="pixel count.*exceeds"):
            printer._load_image(img)

    def test_error_message_includes_dimensions(self):
        """Test that error message shows the problematic dimensions."""
        from p31s.printer import MAX_IMAGE_DIMENSION

        printer = P31SPrinter()
        img = Image.new("1", (15000, 200), color=1)
        with pytest.raises(ImageError) as exc_info:
            printer._load_image(img)
        assert "15000x200" in str(exc_info.value)
        assert str(MAX_IMAGE_DIMENSION) in str(exc_info.value)

    def test_error_message_includes_pixel_count(self):
        """Test that error message shows the pixel count."""

        printer = P31SPrinter()
        img = Image.new("1", (5000, 2001), color=1)
        with pytest.raises(ImageError) as exc_info:
            printer._load_image(img)
        assert "10,005,000" in str(exc_info.value)
        assert "10,000,000" in str(exc_info.value)


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
        mock_connection.write_chunked = AsyncMock(side_effect=[False, False, True])

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
    async def test_connection_lost_during_retry_raises_connection_error(self, mock_connection):
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
        printer.connection.connect = AsyncMock(side_effect=[False, False, True])
        printer.connection.write = AsyncMock(return_value=True)
        printer.connection.read_response = AsyncMock(return_value=None)

        result = await printer.connect("AA:BB:CC:DD:EE:FF", retries=2, retry_delay=0.01)
        assert result is True
        assert printer.connection.connect.call_count == 3


class TestQuickPrint:
    """Test quick_print convenience function."""

    @pytest.mark.asyncio
    async def test_connection_failure_raises(self):
        """Test that connection failure raises ConnectionError."""
        with patch.object(P31SPrinter, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = False
            with patch.object(P31SPrinter, "disconnect", new_callable=AsyncMock):
                with pytest.raises(ConnectionError):
                    await quick_print("AA:BB:CC:DD:EE:FF", "/some/image.png")


class TestBluetoothAddressValidation:
    """Test Bluetooth MAC address validation."""

    # Valid address formats
    @pytest.mark.parametrize(
        "address",
        [
            "AA:BB:CC:DD:EE:FF",  # Uppercase
            "aa:bb:cc:dd:ee:ff",  # Lowercase
            "Aa:Bb:Cc:Dd:Ee:Ff",  # Mixed case
            "00:00:00:00:00:00",  # All zeros
            "FF:FF:FF:FF:FF:FF",  # All max
            "12:34:56:78:9A:BC",  # Mixed hex digits
        ],
    )
    def test_valid_address_pattern(self, address):
        """Test that valid addresses match the pattern."""
        assert BLUETOOTH_MAC_PATTERN.match(address) is not None

    # Invalid address formats
    @pytest.mark.parametrize(
        "address,description",
        [
            ("", "empty string"),
            ("AA:BB:CC:DD:EE", "too short (5 segments)"),
            ("AA:BB:CC:DD:EE:FF:00", "too long (7 segments)"),
            ("AABBCCDDEEFF", "no colons"),
            ("AA-BB-CC-DD-EE-FF", "dashes instead of colons"),
            ("AA:BB:CC:DD:EE:GG", "invalid hex character G"),
            ("AA:BB:CC:DD:EE:FFF", "segment too long"),
            ("AA:BB:CC:DD:EE:F", "segment too short"),
            ("AA:BB:CC:DD:EE:", "trailing colon"),
            (":AA:BB:CC:DD:EE:FF", "leading colon"),
            ("AA:BB:CC:DD:EE:FF ", "trailing space"),
            (" AA:BB:CC:DD:EE:FF", "leading space"),
            ("random-text", "random text"),
            ("192.168.1.1", "IP address format"),
        ],
    )
    def test_invalid_address_pattern(self, address, description):
        """Test that invalid addresses don't match the pattern."""
        assert BLUETOOTH_MAC_PATTERN.match(address) is None, f"Should reject: {description}"

    @pytest.mark.asyncio
    async def test_connect_rejects_invalid_address(self):
        """Test that connect() raises ValueError for invalid address."""
        printer = P31SPrinter()
        with pytest.raises(ValueError, match="Invalid Bluetooth address"):
            await printer.connect("invalid-address")

    @pytest.mark.asyncio
    async def test_connect_rejects_empty_address(self):
        """Test that connect() raises ValueError for empty address."""
        printer = P31SPrinter()
        with pytest.raises(ValueError, match="Invalid Bluetooth address"):
            await printer.connect("")

    @pytest.mark.asyncio
    async def test_connect_accepts_valid_address(self):
        """Test that connect() accepts valid address format."""
        printer = P31SPrinter()
        printer.connection = MagicMock()
        printer.connection.connect = AsyncMock(return_value=True)
        printer.connection.write = AsyncMock(return_value=True)
        printer.connection.read_response = AsyncMock(return_value=None)

        # Should not raise ValueError
        result = await printer.connect("AA:BB:CC:DD:EE:FF")
        assert result is True
