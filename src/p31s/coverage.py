"""
Coverage test pattern generator for P31S label printer.

Generates test patterns to validate print area boundaries.
"""

from PIL import Image, ImageDraw


def generate_coverage_pattern(
    width: int = 96,
    height: int = 304,
    border_width: int = 2,
    grid_spacing: int = 20,
) -> Image.Image:
    """
    Generate a coverage test pattern for print area validation.

    The pattern includes:
    - Border rectangle at the edges
    - Corner markers (filled squares)
    - Center crosshair
    - Grid tick marks for measurement

    Args:
        width: Pattern width in pixels (default 96 per iOS capture)
        height: Pattern height in pixels (default 304 per iOS capture)
        border_width: Border line thickness in pixels
        grid_spacing: Spacing between grid tick marks in pixels

    Returns:
        PIL Image with 1-bit test pattern (mode "1")
    """
    img = Image.new("1", (width, height), color=1)  # White background
    draw = ImageDraw.Draw(img)

    # Draw border rectangle
    draw.rectangle(
        [0, 0, width - 1, height - 1],
        outline=0,
        width=border_width,
    )

    # Draw corner markers (small filled squares)
    corner_size = 8
    corners = [
        (0, 0),  # Top-left
        (width - corner_size, 0),  # Top-right
        (0, height - corner_size),  # Bottom-left
        (width - corner_size, height - corner_size),  # Bottom-right
    ]
    for cx, cy in corners:
        draw.rectangle([cx, cy, cx + corner_size - 1, cy + corner_size - 1], fill=0)

    # Draw center crosshair
    center_x, center_y = width // 2, height // 2
    crosshair_size = 10
    # Horizontal line
    draw.line(
        [(center_x - crosshair_size, center_y), (center_x + crosshair_size, center_y)],
        fill=0,
        width=1,
    )
    # Vertical line
    draw.line(
        [(center_x, center_y - crosshair_size), (center_x, center_y + crosshair_size)],
        fill=0,
        width=1,
    )

    # Draw grid tick marks along edges
    tick_length = 4

    # Horizontal ticks (along top and bottom)
    for x in range(grid_spacing, width, grid_spacing):
        # Top edge
        draw.line([(x, 0), (x, tick_length)], fill=0)
        # Bottom edge
        draw.line([(x, height - tick_length - 1), (x, height - 1)], fill=0)

    # Vertical ticks (along left and right)
    for y in range(grid_spacing, height, grid_spacing):
        # Left edge
        draw.line([(0, y), (tick_length, y)], fill=0)
        # Right edge
        draw.line([(width - tick_length - 1, y), (width - 1, y)], fill=0)

    return img
