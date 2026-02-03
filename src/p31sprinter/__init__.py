"""P31S Label Printer Driver for Linux/macOS."""

__version__ = "0.1.0"

from .printer import (
    P31SPrinter,
    PrinterError,
    ConnectionError,
    PrintError,
    PaperError,
    ImageError,
)
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
