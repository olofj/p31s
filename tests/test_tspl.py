"""Tests for TSPL protocol implementation."""

import pytest
from PIL import Image

from p31sprinter.tspl import (
    TSPLCommand, LabelSize, Density, BitmapMode, Direction, create_print_job
)


class TestTSPLCommand:
    """Test TSPL command generation."""

    def test_size_command(self):
        """Test SIZE command generation."""
        cmd = TSPLCommand()
        cmd.size(15.0, 10.0)
        assert cmd.get_commands() == b"SIZE 15.0 mm,10.0 mm\r\n"

    def test_gap_command(self):
        """Test GAP command generation."""
        cmd = TSPLCommand()
        cmd.gap(2.0)
        assert cmd.get_commands() == b"GAP 2.0 mm,0 mm\r\n"

    def test_density_command(self):
        """Test DENSITY command generation."""
        cmd = TSPLCommand()
        cmd.density(Density.LEVEL_8)
        assert cmd.get_commands() == b"DENSITY 8\r\n"

    def test_cls_command(self):
        """Test CLS command generation."""
        cmd = TSPLCommand()
        cmd.cls()
        assert cmd.get_commands() == b"CLS\r\n"

    def test_direction_command(self):
        """Test DIRECTION command generation."""
        cmd = TSPLCommand()
        cmd.direction(Direction.FORWARD)
        assert cmd.get_commands() == b"DIRECTION 0,0\r\n"

    def test_bar_command(self):
        """Test BAR command generation."""
        cmd = TSPLCommand()
        cmd.bar(10, 20, 100, 50)
        assert cmd.get_commands() == b"BAR 10,20,100,50\r\n"

    def test_text_command(self):
        """Test TEXT command generation."""
        cmd = TSPLCommand()
        cmd.text(10, 20, "1", 0, 1, 1, "Hello")
        assert cmd.get_commands() == b'TEXT 10,20,"1",0,1,1,"Hello"\r\n'

    def test_qrcode_command(self):
        """Test QRCODE command generation."""
        cmd = TSPLCommand()
        cmd.qrcode(10, 20, "M", 4, "A", 0, "https://example.com")
        assert cmd.get_commands() == b'QRCODE 10,20,M,4,A,0,"https://example.com"\r\n'

    def test_print_command(self):
        """Test PRINT command generation."""
        cmd = TSPLCommand()
        cmd.print_label(2, 3)
        assert cmd.get_commands() == b"PRINT 2,3\r\n"

    def test_multiple_commands(self):
        """Test chaining multiple commands."""
        cmd = TSPLCommand()
        cmd.size(15.0, 10.0)
        cmd.gap(2.0)
        cmd.cls()
        cmd.print_label(1)

        expected = b"SIZE 15.0 mm,10.0 mm\r\nGAP 2.0 mm,0 mm\r\nCLS\r\nPRINT 1,1\r\n"
        assert cmd.get_commands() == expected

    def test_clear(self):
        """Test clearing commands."""
        cmd = TSPLCommand()
        cmd.cls()
        assert len(cmd.get_commands()) > 0
        cmd.clear()
        assert cmd.get_commands() == b""


class TestBitmapCommand:
    """Test bitmap-related TSPL commands."""

    def test_bitmap_command(self):
        """Test BITMAP command generation."""
        cmd = TSPLCommand()
        data = bytes([0xFF, 0x00, 0xFF, 0x00])  # 2x2 pixels
        cmd.bitmap(10, 20, 1, 4, BitmapMode.OVERWRITE, data)

        result = cmd.get_commands()
        assert result.startswith(b"BITMAP 10,20,1,4,0,")
        assert result.endswith(b"\r\n")
        # Data should be embedded
        assert b"\xff\x00\xff\x00" in result

    def test_bitmap_from_image(self):
        """Test converting PIL Image to bitmap command."""
        cmd = TSPLCommand()

        # Create 8x2 test image (fits in 1 byte width)
        img = Image.new("1", (8, 2), color=255)  # White background
        # Draw black line on first row
        for x in range(8):
            img.putpixel((x, 0), 0)

        cmd.bitmap_from_image(0, 0, img)
        result = cmd.get_commands()

        # Should have BITMAP command
        assert b"BITMAP 0,0,1,2,0," in result

    def test_bitmap_from_rgb_image(self):
        """Test converting RGB image to bitmap command."""
        cmd = TSPLCommand()

        # Create RGB image
        img = Image.new("RGB", (8, 2), color=(255, 255, 255))

        # Should convert to 1-bit automatically
        cmd.bitmap_from_image(0, 0, img)
        result = cmd.get_commands()

        assert b"BITMAP" in result


class TestConvenienceMethods:
    """Test convenience methods."""

    def test_setup_label(self):
        """Test setup_label convenience method."""
        cmd = TSPLCommand()
        label = LabelSize(width=15.0, height=10.0, gap=2.0)
        cmd.setup_label(label, Density.LEVEL_10)

        result = cmd.get_commands()
        assert b"SIZE 15.0 mm,10.0 mm" in result
        assert b"GAP 2.0 mm" in result
        assert b"DENSITY 10" in result
        assert b"CLS" in result

    def test_create_print_job(self):
        """Test create_print_job function."""
        label = LabelSize(width=15.0, height=10.0)
        img = Image.new("1", (96, 64), color=255)

        result = create_print_job(label, img, Density.LEVEL_8, copies=2)

        assert b"SIZE 15.0 mm,10.0 mm" in result
        assert b"BITMAP" in result
        assert b"PRINT 1,2" in result


class TestLabelSize:
    """Test LabelSize dataclass."""

    def test_default_gap(self):
        """Test default gap value."""
        label = LabelSize(width=15.0, height=10.0)
        assert label.gap == 2.0

    def test_custom_gap(self):
        """Test custom gap value."""
        label = LabelSize(width=15.0, height=10.0, gap=3.0)
        assert label.gap == 3.0
