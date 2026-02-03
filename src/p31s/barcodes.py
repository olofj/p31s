"""
Barcode and QR Code Generation for P31S Printer.

Requires optional dependencies:
    pip install p31s[barcodes]
"""

from io import BytesIO
from typing import Literal, Optional

from PIL import Image

# Barcode types supported
BarcodeType = Literal["code128", "code39", "ean13", "upca"]

# QR code error correction levels
QRErrorCorrection = Literal["L", "M", "Q", "H"]

# QR code size presets (box_size, border)
QR_SIZES = {
    "small": (2, 2),
    "medium": (4, 4),
    "large": (6, 4),
}


def _check_barcode_dependency() -> None:
    """Check that python-barcode is installed."""
    try:
        import barcode  # noqa: F401
    except ImportError:
        raise ImportError(
            "python-barcode is required for barcode generation. "
            "Install with: pip install p31s[barcodes]"
        ) from None


def _check_qrcode_dependency() -> None:
    """Check that qrcode is installed."""
    try:
        import qrcode  # noqa: F401
    except ImportError:
        raise ImportError(
            "qrcode is required for QR code generation. Install with: pip install p31s[barcodes]"
        ) from None


def generate_barcode(
    data: str,
    barcode_type: BarcodeType = "code128",
    width: Optional[int] = None,
    height: int = 50,
    include_text: bool = True,
) -> Image.Image:
    """
    Generate a barcode image.

    Args:
        data: The data to encode in the barcode
        barcode_type: Type of barcode (code128, code39, ean13, upca)
        width: Target width in pixels (None for auto-sizing)
        height: Height of barcode bars in pixels
        include_text: Whether to include human-readable text below barcode

    Returns:
        PIL Image in 1-bit mode (black and white)

    Raises:
        ImportError: If python-barcode is not installed
        ValueError: If barcode_type is invalid or data cannot be encoded
    """
    _check_barcode_dependency()

    import barcode
    from barcode.writer import ImageWriter

    # Map our types to python-barcode types
    type_map = {
        "code128": "code128",
        "code39": "code39",
        "ean13": "ean13",
        "upca": "upca",
    }

    if barcode_type not in type_map:
        raise ValueError(
            f"Invalid barcode type: {barcode_type}. Supported types: {list(type_map.keys())}"
        )

    barcode_class = barcode.get_barcode_class(type_map[barcode_type])

    # Configure the writer
    writer = ImageWriter()
    options = {
        "module_height": height / 10,  # Convert pixels to mm (approx)
        "write_text": include_text,
        "font_size": 8 if include_text else 0,
        "text_distance": 2,
        "quiet_zone": 2,
    }

    # Create the barcode
    bc = barcode_class(data, writer=writer)
    buffer = BytesIO()
    bc.write(buffer, options=options)
    buffer.seek(0)

    # Load and convert to 1-bit
    img = Image.open(buffer)
    img = img.convert("L")  # Grayscale first

    # Resize if width specified
    if width is not None:
        ratio = width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((width, new_height), Image.Resampling.LANCZOS)

    # Convert to 1-bit with threshold
    img = img.point(lambda x: 0 if x < 128 else 255, mode="1")

    return img


def generate_qr(
    data: str,
    size: Literal["small", "medium", "large"] = "medium",
    error_correction: QRErrorCorrection = "M",
) -> Image.Image:
    """
    Generate a QR code image.

    Args:
        data: The data to encode (URL, text, etc.)
        size: Size preset (small, medium, large)
        error_correction: Error correction level (L=7%, M=15%, Q=25%, H=30%)

    Returns:
        PIL Image in 1-bit mode (black and white)

    Raises:
        ImportError: If qrcode is not installed
        ValueError: If size is invalid or data cannot be encoded
    """
    _check_qrcode_dependency()

    import qrcode
    from qrcode.constants import (
        ERROR_CORRECT_H,
        ERROR_CORRECT_L,
        ERROR_CORRECT_M,
        ERROR_CORRECT_Q,
    )

    if size not in QR_SIZES:
        raise ValueError(f"Invalid size: {size}. Supported sizes: {list(QR_SIZES.keys())}")

    # Map error correction levels
    ec_map = {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }

    box_size, border = QR_SIZES[size]

    qr = qrcode.QRCode(
        version=None,  # Auto-detect version based on data
        error_correction=ec_map[error_correction],
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Generate image
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to PIL Image if needed (qrcode returns PilImage wrapper)
    if hasattr(img, "get_image"):
        img = img.get_image()

    # Ensure 1-bit mode
    if img.mode != "1":
        img = img.convert("1")

    return img
