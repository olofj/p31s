"""
Image Processing for P31S Printer.

Converts images to 1-bit monochrome bitmap format suitable for
thermal printing at 203 DPI.
"""

from io import BytesIO
from pathlib import Path
from typing import Iterator, Union

from PIL import Image

# Image size limits to prevent memory exhaustion from malicious/malformed images
MAX_IMAGE_DIMENSION = 10000  # Maximum width or height in pixels
MAX_IMAGE_PIXELS = 10_000_000  # Maximum total pixels (10 megapixels)


class ImageSizeError(ValueError):
    """Image dimensions exceed safety limits."""

    pass


class ImageProcessor:
    """Process images for thermal printing."""

    # P31S printer specifications (203 DPI)
    DPI = 203
    MAX_WIDTH_MM = 15  # Maximum printable width in mm
    MAX_WIDTH_PIXELS = int(MAX_WIDTH_MM * DPI / 25.4)  # ~120 pixels

    def __init__(self, width: int = MAX_WIDTH_PIXELS, threshold: int = 128):
        """
        Initialize processor.

        Args:
            width: Target width in pixels (default: max for 15mm tape)
            threshold: Grayscale threshold for black/white conversion (0-255)
        """
        self.width = width
        self.threshold = threshold

    def load(self, source: Union[str, Path, bytes, Image.Image]) -> Image.Image:
        """
        Load an image from various sources.

        Args:
            source: File path, bytes, or PIL Image

        Returns:
            PIL Image object

        Raises:
            ImageSizeError: If image dimensions exceed safety limits
            ValueError: If source type is unsupported
        """
        if isinstance(source, Image.Image):
            img = source
        elif isinstance(source, (str, Path)):
            img = Image.open(source)
        elif isinstance(source, bytes):
            img = Image.open(BytesIO(source))
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        # Validate image dimensions to prevent memory exhaustion
        if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
            raise ImageSizeError(
                f"Image dimensions ({img.width}x{img.height}) exceed maximum "
                f"({MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION})"
            )
        if img.width * img.height > MAX_IMAGE_PIXELS:
            raise ImageSizeError(
                f"Image pixel count ({img.width * img.height:,}) exceeds "
                f"maximum ({MAX_IMAGE_PIXELS:,})"
            )

        return img

    def prepare(self, image: Image.Image, rotate: bool = False) -> Image.Image:
        """
        Prepare image for printing.

        Args:
            image: Source image
            rotate: Rotate 90 degrees (for portrait labels)

        Returns:
            Processed 1-bit image
        """
        # Convert to grayscale if needed
        if image.mode != "L":
            image = image.convert("L")

        # Rotate if requested
        if rotate:
            image = image.rotate(90, expand=True)

        # Resize to fit printer width while maintaining aspect ratio
        if image.width != self.width:
            ratio = self.width / image.width
            new_height = int(image.height * ratio)
            image = image.resize((self.width, new_height), Image.Resampling.LANCZOS)

        # Convert to 1-bit using threshold
        # Note: For thermal printing, black pixels are where heat is applied
        image = image.point(lambda x: 0 if x < self.threshold else 255, mode="1")

        return image

    def _get_pixels(self, image: Image.Image) -> list:
        """Get pixel data from image without using deprecated methods."""
        if image.mode != "1":
            image = image.convert("1")

        width = image.width
        height = image.height
        pixels = []

        for y in range(height):
            for x in range(width):
                pixels.append(image.getpixel((x, y)))

        return pixels

    def to_bytes(self, image: Image.Image) -> bytes:
        """
        Convert 1-bit image to raw bitmap bytes.

        Returns packed bytes where each bit represents a pixel.
        MSB is leftmost pixel. Black pixels are 1, white are 0.
        """
        if image.mode != "1":
            image = image.convert("1")

        width = image.width
        height = image.height

        # Calculate bytes per row (rounded up to nearest byte)
        bytes_per_row = (width + 7) // 8

        result = bytearray()

        for row in range(height):
            row_byte = 0
            bit_pos = 7

            for col in range(width):
                pixel = image.getpixel((col, row))
                # In PIL "1" mode, 0 is black, 255 is white
                # For thermal printer: 1 = burn (black), 0 = no burn (white)
                if pixel == 0:  # Black pixel
                    row_byte |= (1 << bit_pos)

                bit_pos -= 1
                if bit_pos < 0:
                    result.append(row_byte)
                    row_byte = 0
                    bit_pos = 7

            # Pad last byte of row if needed
            if bit_pos != 7:
                result.append(row_byte)

            # Pad row to full byte width if needed
            while len(result) % bytes_per_row != 0 or len(result) == 0:
                result.append(0)

        return bytes(result)

    def iter_rows(self, image: Image.Image) -> Iterator[bytes]:
        """
        Iterate over image rows as bytes.

        Yields one row of packed bytes at a time.
        """
        if image.mode != "1":
            image = image.convert("1")

        width = image.width
        height = image.height
        bytes_per_row = (width + 7) // 8

        for row in range(height):
            row_bytes = bytearray()
            row_byte = 0
            bit_pos = 7

            for col in range(width):
                pixel = image.getpixel((col, row))
                if pixel == 0:  # Black pixel
                    row_byte |= (1 << bit_pos)

                bit_pos -= 1
                if bit_pos < 0:
                    row_bytes.append(row_byte)
                    row_byte = 0
                    bit_pos = 7

            # Handle partial last byte
            if bit_pos != 7:
                row_bytes.append(row_byte)

            # Pad to full width
            while len(row_bytes) < bytes_per_row:
                row_bytes.append(0)

            yield bytes(row_bytes)

    def count_empty_rows(self, rows: list[bytes]) -> list[tuple]:
        """
        Compress consecutive empty rows.

        Returns list of tuples:
            - ("data", bytes): Row with data
            - ("empty", int): Count of consecutive empty rows
        """
        result = []
        empty_count = 0
        empty_row = bytes(len(rows[0])) if rows else b""

        for row in rows:
            if row == empty_row:
                empty_count += 1
            else:
                if empty_count > 0:
                    result.append(("empty", empty_count))
                    empty_count = 0
                result.append(("data", row))

        if empty_count > 0:
            result.append(("empty", empty_count))

        return result


def create_test_pattern(width: int = 96, height: int = 96) -> Image.Image:
    """Create a simple test pattern image."""
    img = Image.new("1", (width, height), color=1)  # White background

    # Draw a border
    for x in range(width):
        img.putpixel((x, 0), 0)
        img.putpixel((x, height - 1), 0)
    for y in range(height):
        img.putpixel((0, y), 0)
        img.putpixel((width - 1, y), 0)

    # Draw diagonal lines
    for i in range(min(width, height)):
        img.putpixel((i, i), 0)
        img.putpixel((width - 1 - i, i), 0)

    return img
