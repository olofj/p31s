"""P31S Label Printer Driver for Linux/macOS."""

__version__ = "0.1.0"

from .printer import (
    P31SPrinter,
    PrinterError,
    ConnectionError,
    PrintError,
    PaperError,
    ImageError,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
)
from .image import ImageSizeError
from .connection import BLEConnection
from .tspl import TSPLCommand, LabelSize, Density, BitmapMode
from .tspl_commands import TSPLCommands
from .responses import PrinterConfig, BatteryStatus, ChunkSize, PrintedCount

__all__ = [
    "P31SPrinter",
    "PrinterError",
    "ConnectionError",
    "PrintError",
    "PaperError",
    "ImageError",
    "ImageSizeError",
    "MAX_IMAGE_DIMENSION",
    "MAX_IMAGE_PIXELS",
    "BLEConnection",
    "TSPLCommand",
    "LabelSize",
    "Density",
    "BitmapMode",
    "TSPLCommands",
    "PrinterConfig",
    "BatteryStatus",
    "ChunkSize",
    "PrintedCount",
]
