"""
TSPL Text-Based Status Commands for P31S Printer.

This module provides text-based commands for querying printer status,
as discovered from the decompiled Labelnize APK (O8.java).

Unlike the binary NIIMBOT protocol, the P31S uses simple ASCII text
commands terminated with CRLF.
"""

from enum import IntEnum


class CommandType(IntEnum):
    """Command type identifiers from O8.java."""
    CONFIG = 10
    INITIALIZE = 11
    SELFTEST = 12
    BATTERY = 13
    CHUNK_SIZE = 16
    PRINTED_COUNT = 35


class TSPLCommands:
    """
    Text-based status command builders for P31S printer.

    All commands are ASCII strings terminated with CRLF (\\r\\n).
    """

    CRLF = b"\r\n"

    @staticmethod
    def config_query() -> bytes:
        """
        Query printer configuration and firmware version.

        Returns device info including:
        - Resolution
        - Hardware version
        - Firmware version
        - Shutdown timer setting
        - Sound setting

        Response: 19 or 20 bytes (see responses.PrinterConfig.parse)
        """
        return b"CONFIG?" + TSPLCommands.CRLF

    @staticmethod
    def battery_query() -> bytes:
        """
        Query battery status.

        Returns battery level and charging status.

        Response: 11 or 12 bytes (see responses.BatteryStatus.parse)
        """
        return b"BATTERY?" + TSPLCommands.CRLF

    @staticmethod
    def selftest() -> bytes:
        """
        Trigger self-test print.

        Prints a test page with device info and patterns.
        """
        return b"SELFTEST" + TSPLCommands.CRLF

    @staticmethod
    def initialize() -> bytes:
        """
        Initialize the printer.

        Should be called after connecting to reset printer state.
        """
        return b"INITIALPRINTER" + TSPLCommands.CRLF

    @staticmethod
    def get_chunk_size() -> bytes:
        """
        Query the maximum chunk size for data transfers.

        Returns the maximum number of bytes that can be sent
        in a single write operation.
        """
        return b"GETCHUNKSIZE" + TSPLCommands.CRLF

    @staticmethod
    def get_printed_count() -> bytes:
        """
        Query the total print counter.

        Returns the number of labels/pages printed by this device.
        """
        return b"GETPRINTEDCOUNT" + TSPLCommands.CRLF
