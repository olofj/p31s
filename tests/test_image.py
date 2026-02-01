"""Tests for image processing."""

import pytest
from PIL import Image

from p31printer.image import ImageProcessor, create_test_pattern


class TestImageProcessor:
    """Test image processing functionality."""

    def test_to_bytes_simple(self):
        """Test converting a simple image to bytes."""
        processor = ImageProcessor(width=8)

        # Create 8x2 image: first row all black, second row all white
        img = Image.new("1", (8, 2), color=1)  # White
        for x in range(8):
            img.putpixel((x, 0), 0)  # Black first row

        data = processor.to_bytes(img)

        # First row: 8 black pixels = 0xFF
        # Second row: 8 white pixels = 0x00
        assert data == bytes([0xFF, 0x00])

    def test_to_bytes_pattern(self):
        """Test alternating pattern."""
        processor = ImageProcessor(width=8)

        # Create 8x1 image: alternating black/white
        img = Image.new("1", (8, 1), color=1)
        for x in range(0, 8, 2):
            img.putpixel((x, 0), 0)  # Black at even positions

        data = processor.to_bytes(img)

        # Pattern: B W B W B W B W = 10101010 = 0xAA
        assert data == bytes([0xAA])

    def test_to_bytes_partial_byte(self):
        """Test image width not multiple of 8."""
        processor = ImageProcessor(width=12)

        # Create 12x1 image: all black
        img = Image.new("1", (12, 1), color=0)  # Black

        data = processor.to_bytes(img)

        # 12 bits = 2 bytes, padded: 11111111 11110000
        assert len(data) == 2
        assert data[0] == 0xFF
        assert data[1] == 0xF0

    def test_iter_rows(self):
        """Test row iteration."""
        processor = ImageProcessor(width=8)

        # 8x3 image
        img = Image.new("1", (8, 3), color=1)
        img.putpixel((0, 0), 0)  # First pixel black in row 0
        img.putpixel((7, 1), 0)  # Last pixel black in row 1
        # Row 2 all white

        rows = list(processor.iter_rows(img))

        assert len(rows) == 3
        assert rows[0] == bytes([0x80])  # 10000000
        assert rows[1] == bytes([0x01])  # 00000001
        assert rows[2] == bytes([0x00])  # 00000000

    def test_count_empty_rows(self):
        """Test empty row compression."""
        processor = ImageProcessor(width=8)

        rows = [
            bytes([0x00]),  # empty
            bytes([0x00]),  # empty
            bytes([0xFF]),  # data
            bytes([0x00]),  # empty
            bytes([0x00]),  # empty
            bytes([0x00]),  # empty
            bytes([0xAA]),  # data
        ]

        compressed = processor.count_empty_rows(rows)

        assert compressed == [
            ("empty", 2),
            ("data", bytes([0xFF])),
            ("empty", 3),
            ("data", bytes([0xAA])),
        ]

    def test_prepare_resize(self):
        """Test image resizing."""
        processor = ImageProcessor(width=100, threshold=128)

        # Create large image
        img = Image.new("L", (200, 100), color=128)

        prepared = processor.prepare(img)

        assert prepared.width == 100
        assert prepared.height == 50  # Aspect ratio preserved
        assert prepared.mode == "1"

    def test_prepare_threshold(self):
        """Test threshold conversion."""
        processor = ImageProcessor(width=4, threshold=128)

        # Create grayscale image
        img = Image.new("L", (4, 1))
        img.putpixel((0, 0), 0)    # Black
        img.putpixel((1, 0), 127)  # Below threshold -> black
        img.putpixel((2, 0), 128)  # At threshold -> white
        img.putpixel((3, 0), 255)  # White

        prepared = processor.prepare(img)

        # Check pixels: 0,1 should be black (0), 2,3 should be white (255)
        assert prepared.getpixel((0, 0)) == 0
        assert prepared.getpixel((1, 0)) == 0
        assert prepared.getpixel((2, 0)) == 255
        assert prepared.getpixel((3, 0)) == 255


class TestCreateTestPattern:
    """Test test pattern generation."""

    def test_creates_image(self):
        """Test that test pattern is created correctly."""
        pattern = create_test_pattern(width=32, height=32)

        assert pattern.mode == "1"
        assert pattern.width == 32
        assert pattern.height == 32

    def test_has_border(self):
        """Test that pattern has a border."""
        pattern = create_test_pattern(width=32, height=32)

        # Top-left corner should be black (border)
        assert pattern.getpixel((0, 0)) == 0
        # Center should be white (or diagonal line)
        # Just verify it's a valid image
        assert pattern.getpixel((1, 1)) in (0, 255)

    def test_default_size(self):
        """Test default size."""
        pattern = create_test_pattern()

        assert pattern.width == 96
        assert pattern.height == 96
