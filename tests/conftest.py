"""
Pytest configuration for P31S printer tests.

Provides fixtures and command-line options for hardware tests.
"""

import pytest
import pytest_asyncio

from p31sprinter import P31SPrinter


def pytest_addoption(parser):
    """Add command-line options for hardware tests."""
    parser.addoption(
        "--address",
        action="store",
        default=None,
        help="Bluetooth address of the printer for hardware tests",
    )


@pytest.fixture
def printer_address(request):
    """Get the printer address from command line."""
    address = request.config.getoption("--address")
    if address is None:
        pytest.skip("No printer address provided (use --address=XX:XX:XX:XX:XX:XX)")
    return address


@pytest_asyncio.fixture
async def connected_printer(printer_address):
    """Provide a connected printer instance."""
    printer = P31SPrinter()
    printer.set_debug(True)

    if not await printer.connect(printer_address, retries=2, retry_delay=1.0):
        pytest.skip(f"Could not connect to printer at {printer_address}")

    yield printer

    await printer.disconnect()
