"""Tests for barcode and QR code generation."""

import pytest
from PIL import Image

# Mark all tests as requiring barcode dependencies
pytestmark = pytest.mark.barcodes


class TestGenerateBarcode:
    """Test barcode generation functionality."""

    def test_generate_code128(self):
        """Test Code128 barcode generation."""
        from p31s.barcodes import generate_barcode

        img = generate_barcode("12345", barcode_type="code128")

        assert isinstance(img, Image.Image)
        assert img.mode == "1"
        assert img.width > 0
        assert img.height > 0

    def test_generate_code39(self):
        """Test Code39 barcode generation."""
        from p31s.barcodes import generate_barcode

        img = generate_barcode("HELLO", barcode_type="code39")

        assert isinstance(img, Image.Image)
        assert img.mode == "1"

    def test_generate_ean13(self):
        """Test EAN-13 barcode generation."""
        from p31s.barcodes import generate_barcode

        # EAN-13 requires 12-13 digits
        img = generate_barcode("123456789012", barcode_type="ean13")

        assert isinstance(img, Image.Image)
        assert img.mode == "1"

    def test_generate_upca(self):
        """Test UPC-A barcode generation."""
        from p31s.barcodes import generate_barcode

        # UPC-A requires 11-12 digits
        img = generate_barcode("12345678901", barcode_type="upca")

        assert isinstance(img, Image.Image)
        assert img.mode == "1"

    def test_barcode_no_text(self):
        """Test barcode without human-readable text."""
        from p31s.barcodes import generate_barcode

        img_with_text = generate_barcode("12345", include_text=True)
        img_no_text = generate_barcode("12345", include_text=False)

        # Image without text should be shorter
        assert img_no_text.height < img_with_text.height

    def test_barcode_custom_width(self):
        """Test barcode with custom width."""
        from p31s.barcodes import generate_barcode

        img = generate_barcode("12345", width=100)

        assert img.width == 100

    def test_invalid_barcode_type(self):
        """Test that invalid barcode type raises ValueError."""
        from p31s.barcodes import generate_barcode

        with pytest.raises(ValueError, match="Invalid barcode type"):
            generate_barcode("12345", barcode_type="invalid")


class TestGenerateQR:
    """Test QR code generation functionality."""

    def test_generate_qr_url(self):
        """Test QR code generation with URL."""
        from p31s.barcodes import generate_qr

        img = generate_qr("https://example.com")

        assert isinstance(img, Image.Image)
        assert img.mode == "1"
        # QR codes are square
        assert img.width == img.height

    def test_generate_qr_text(self):
        """Test QR code generation with text."""
        from p31s.barcodes import generate_qr

        img = generate_qr("Hello, World!")

        assert isinstance(img, Image.Image)
        assert img.mode == "1"

    def test_qr_sizes(self):
        """Test different QR code sizes."""
        from p31s.barcodes import generate_qr

        small = generate_qr("test", size="small")
        medium = generate_qr("test", size="medium")
        large = generate_qr("test", size="large")

        assert small.width < medium.width < large.width

    def test_qr_error_correction_levels(self):
        """Test different error correction levels."""
        from p31s.barcodes import generate_qr

        # All levels should produce valid images
        for level in ["L", "M", "Q", "H"]:
            img = generate_qr("test", error_correction=level)
            assert isinstance(img, Image.Image)
            assert img.mode == "1"

    def test_invalid_qr_size(self):
        """Test that invalid size raises ValueError."""
        from p31s.barcodes import generate_qr

        with pytest.raises(ValueError, match="Invalid size"):
            generate_qr("test", size="invalid")

    def test_qr_long_data(self):
        """Test QR code with longer data."""
        from p31s.barcodes import generate_qr

        long_url = "https://example.com/path/to/resource?param1=value1&param2=value2"
        img = generate_qr(long_url)

        assert isinstance(img, Image.Image)
        # Longer data produces larger QR codes
        short = generate_qr("hi")
        assert img.width >= short.width


class TestDependencyChecks:
    """Test dependency checking behavior."""

    def test_barcode_import_works(self):
        """Test that barcode imports work when dependencies are installed."""
        from p31s.barcodes import generate_barcode

        # If we get here, import succeeded
        img = generate_barcode("test")
        assert img is not None

    def test_qr_import_works(self):
        """Test that qrcode imports work when dependencies are installed."""
        from p31s.barcodes import generate_qr

        # If we get here, import succeeded
        img = generate_qr("test")
        assert img is not None
