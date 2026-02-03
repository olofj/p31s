"""P31S Label Printer Driver for Linux/macOS."""

__version__ = "0.1.0"

from .connection import BLEConnection, PrinterInfo
from .image import ImageSizeError
from .printer import (
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    ConnectionError,
    ImageError,
    P31SPrinter,
    PaperError,
    PrinterError,
    PrintError,
)
from .responses import BatteryStatus, ChunkSize, PrintedCount, PrinterConfig
from .tspl import BitmapMode, Density, LabelSize, TSPLCommand
from .tspl_commands import TSPLCommands

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
    "PrinterInfo",
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
