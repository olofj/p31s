"""Unit tests for coverage pattern generator."""

from p31sprinter.coverage import generate_coverage_pattern


class TestGenerateCoveragePattern:
    """Tests for generate_coverage_pattern function."""

    def test_default_dimensions(self):
        """Test pattern is created with default dimensions."""
        img = generate_coverage_pattern()
        assert img.size == (96, 304)

    def test_custom_dimensions(self):
        """Test pattern is created with custom dimensions."""
        img = generate_coverage_pattern(width=100, height=200)
        assert img.size == (100, 200)

    def test_returns_1bit_image(self):
        """Test that pattern is 1-bit mode."""
        img = generate_coverage_pattern()
        assert img.mode == "1"

    def test_has_white_background(self):
        """Test that pattern has mostly white background."""
        img = generate_coverage_pattern(width=96, height=304)
        # Sample from center area (should be white)
        center_pixel = img.getpixel((48, 100))
        assert center_pixel == 1  # White

    def test_has_border_at_edges(self):
        """Test that border is drawn at edges."""
        img = generate_coverage_pattern(width=96, height=304, border_width=2)
        # Check top-left corner area (should be black - part of border)
        top_edge = img.getpixel((10, 0))
        left_edge = img.getpixel((0, 10))
        assert top_edge == 0  # Black
        assert left_edge == 0  # Black

    def test_has_corner_markers(self):
        """Test that corner markers are present."""
        img = generate_coverage_pattern(width=96, height=304)
        # Top-left corner marker (8x8 filled square)
        assert img.getpixel((2, 2)) == 0  # Black
        # Top-right corner marker
        assert img.getpixel((93, 2)) == 0  # Black
        # Bottom-left corner marker
        assert img.getpixel((2, 301)) == 0  # Black
        # Bottom-right corner marker
        assert img.getpixel((93, 301)) == 0  # Black

    def test_has_center_crosshair(self):
        """Test that center crosshair is present."""
        img = generate_coverage_pattern(width=96, height=304)
        center_x, center_y = 48, 152
        # Center pixel should be black (intersection of crosshair)
        assert img.getpixel((center_x, center_y)) == 0

    def test_has_grid_ticks(self):
        """Test that grid tick marks are present."""
        img = generate_coverage_pattern(width=96, height=304, grid_spacing=20)
        # Tick at x=20 on top edge
        assert img.getpixel((20, 1)) == 0  # Black
        # Tick at y=20 on left edge
        assert img.getpixel((1, 20)) == 0  # Black

    def test_custom_grid_spacing(self):
        """Test grid spacing parameter."""
        img = generate_coverage_pattern(width=96, height=304, grid_spacing=40)
        # Tick at x=40 on top edge (should exist)
        assert img.getpixel((40, 1)) == 0
        # Tick at x=20 on top edge (should NOT exist with 40px spacing)
        # But border is at 0-1, so check position 2
        tick_20 = img.getpixel((20, 2))
        assert tick_20 == 1  # White (no tick at 20 with 40px spacing)

    def test_custom_border_width(self):
        """Test border width parameter."""
        img = generate_coverage_pattern(width=96, height=304, border_width=4)
        # Border should extend 4 pixels
        assert img.getpixel((10, 3)) == 0  # Black (within 4px border)

    def test_small_pattern(self):
        """Test generating a small pattern."""
        img = generate_coverage_pattern(width=32, height=64)
        assert img.size == (32, 64)
        # Should still have border
        assert img.getpixel((0, 0)) == 0

    def test_large_pattern(self):
        """Test generating a large pattern."""
        img = generate_coverage_pattern(width=200, height=500)
        assert img.size == (200, 500)
        # Should have center crosshair
        center_x, center_y = 100, 250
        assert img.getpixel((center_x, center_y)) == 0
