"""
Command-Line Interface for P31S Printer.

Usage:
    p31 scan              - Scan for printers
    p31 discover ADDRESS  - Discover services on a printer
    p31 print ADDRESS IMAGE - Print an image
    p31 test ADDRESS      - Print test pattern
"""

import asyncio
import re
import sys
from typing import Optional

import click

from .printer import (
    P31SPrinter,
    PrinterError,
    ConnectionError,
    PrintError,
    ImageError,
)
from .tspl import Density
from .barcodes import generate_barcode, generate_qr, BarcodeType
from .coverage import generate_coverage_pattern


# Bluetooth MAC address format: XX:XX:XX:XX:XX:XX (hex pairs separated by colons)
BLUETOOTH_MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

# macOS CoreBluetooth UUID format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
MACOS_UUID_PATTERN = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)


def validate_bluetooth_address(ctx, param, value):
    """Validate Bluetooth address format.

    Accepts:
        - MAC address format: XX:XX:XX:XX:XX:XX (Linux/Windows)
        - UUID format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX (macOS)

    Args:
        ctx: Click context
        param: Click parameter
        value: Address value to validate

    Returns:
        The validated address (uppercased for consistency)

    Raises:
        click.BadParameter: If the address format is invalid
    """
    if value is None:
        return None
    if BLUETOOTH_MAC_PATTERN.match(value):
        return value.upper()
    if MACOS_UUID_PATTERN.match(value):
        return value.upper()
    raise click.BadParameter(
        f"Invalid Bluetooth address format: '{value}'. "
        "Expected MAC format XX:XX:XX:XX:XX:XX or "
        "macOS UUID format XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
    )


async def scan_and_select(timeout: float = 10.0) -> Optional[str]:
    """Scan for printers and let user select one interactively.

    Args:
        timeout: Scan timeout in seconds

    Returns:
        Selected printer address, or None if no printer selected
    """
    click.echo(f"Scanning for printers ({timeout}s)...")
    printers = await P31SPrinter.scan(timeout=timeout)

    if not printers:
        click.echo("No printers found.", err=True)
        return None

    # Auto-select when exactly one printer found
    if len(printers) == 1:
        printer = printers[0]
        click.echo(f"Found 1 printer: {printer.name} - using automatically")
        click.echo(f"Address: {printer.address}")
        return printer.address

    # Multiple printers - show numbered menu
    click.echo(f"\nFound {len(printers)} printer(s):\n")
    for i, p in enumerate(printers, 1):
        click.echo(f"  [{i}] {p}")

    # Prompt for selection
    click.echo()
    while True:
        try:
            choice = click.prompt(f"Select printer (1-{len(printers)})", type=int)
            if 1 <= choice <= len(printers):
                selected = printers[choice - 1]
                click.echo(f"Selected: {selected.name}")
                return selected.address
            click.echo(f"Please enter a number between 1 and {len(printers)}", err=True)
        except click.Abort:
            return None


@click.group()
@click.option("--debug/--no-debug", default=False, help="Enable debug output")
@click.pass_context
def main(ctx, debug):
    """P31S Label Printer CLI."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


@main.command()
@click.option("--timeout", default=10.0, help="Scan timeout in seconds")
@click.option(
    "--no-auto",
    is_flag=True,
    help="Don't auto-select when only one printer is found",
)
def scan(timeout, no_auto):
    """Scan for P31S printers.

    When exactly one printer is found, it will be automatically selected
    and its address printed for easy use with other commands.
    Use --no-auto to always show the full list format.
    """

    async def _scan():
        click.echo(f"Scanning for printers ({timeout}s)...")
        printers = await P31SPrinter.scan(timeout=timeout)

        if not printers:
            click.echo("No printers found.")
            return

        # Auto-select when exactly one printer found (unless --no-auto)
        if len(printers) == 1 and not no_auto:
            printer = printers[0]
            click.echo(f"\nFound 1 printer: {printer.name} - using automatically")
            click.echo(f"Address: {printer.address}")
            return

        click.echo(f"\nFound {len(printers)} printer(s):\n")
        for p in printers:
            click.echo(f"  {p}")

    asyncio.run(_scan())


@main.command()
@click.option(
    "--address",
    "-a",
    callback=validate_bluetooth_address,
    help="Printer Bluetooth address (if omitted, scans and prompts)",
)
@click.pass_context
def discover(ctx, address):
    """Discover GATT services on a printer.

    If no address is specified, scans for printers and prompts for selection.
    """

    async def _discover():
        nonlocal address
        if address is None:
            address = await scan_and_select()
            if address is None:
                sys.exit(1)

        printer = P31SPrinter()
        printer.set_debug(ctx.obj["debug"])

        click.echo(f"Connecting to {address}...")

        if not await printer.connect(address):
            click.echo("Failed to connect!", err=True)
            return

        try:
            services = await printer.discover_services()

            click.echo("\nGATT Services:\n")
            for svc in services:
                click.echo(f"Service: {svc.service_uuid}")
                for char in svc.characteristics:
                    props = ", ".join(char["properties"])
                    click.echo(f"  Char: {char['uuid']}")
                    click.echo(f"        Properties: [{props}]")
                click.echo()
        finally:
            await printer.disconnect()

    asyncio.run(_discover())


@main.command("print")
@click.argument("image", type=click.Path(exists=True))
@click.option(
    "--address",
    "-a",
    callback=validate_bluetooth_address,
    help="Printer Bluetooth address (if omitted, scans and prompts)",
)
@click.option(
    "--density",
    type=click.IntRange(0, 15),
    default=8,
    help="Print density (0-15, default 8)",
)
@click.option("--copies", default=1, help="Number of copies")
@click.option("--retry", default=0, help="Number of retries for transient failures")
@click.pass_context
def print_image(ctx, image, address, density, copies, retry):
    """Print an image file.

    If no address is specified, scans for printers and prompts for selection.
    """

    async def _print():
        nonlocal address
        if address is None:
            address = await scan_and_select()
            if address is None:
                sys.exit(1)

        printer = P31SPrinter()
        printer.set_debug(ctx.obj["debug"])

        click.echo(f"Connecting to {address}...")

        try:
            if not await printer.connect(address, retries=retry):
                click.echo("Failed to connect!", err=True)
                sys.exit(1)

            click.echo(f"Printing {image}...")
            success = await printer.print_image(
                image,
                density=Density(density),
                copies=copies,
                retries=retry,
            )

            if success:
                click.echo("Print complete!")
            else:
                click.echo("Print failed!", err=True)
                sys.exit(1)

        except ConnectionError as e:
            click.echo(f"Connection error: {e}", err=True)
            sys.exit(1)
        except ImageError as e:
            click.echo(f"Image error: {e}", err=True)
            sys.exit(1)
        except PrintError as e:
            click.echo(f"Print error: {e}", err=True)
            sys.exit(1)
        except PrinterError as e:
            click.echo(f"Printer error: {e}", err=True)
            sys.exit(1)
        finally:
            await printer.disconnect()

    asyncio.run(_print())


@main.command()
@click.option(
    "--address",
    "-a",
    callback=validate_bluetooth_address,
    help="Printer Bluetooth address (if omitted, scans and prompts)",
)
@click.option("--retry", default=0, help="Number of retries for transient failures")
@click.pass_context
def test(ctx, address, retry):
    """Print a test pattern.

    If no address is specified, scans for printers and prompts for selection.
    """

    async def _test():
        nonlocal address
        if address is None:
            address = await scan_and_select()
            if address is None:
                sys.exit(1)

        printer = P31SPrinter()
        printer.set_debug(ctx.obj["debug"])

        click.echo(f"Connecting to {address}...")

        try:
            if not await printer.connect(address, retries=retry):
                click.echo("Failed to connect!", err=True)
                sys.exit(1)

            click.echo("Printing test pattern...")
            success = await printer.print_test_pattern(retries=retry)

            if success:
                click.echo("Test print complete!")
            else:
                click.echo("Test print failed!", err=True)
                sys.exit(1)

        except ConnectionError as e:
            click.echo(f"Connection error: {e}", err=True)
            sys.exit(1)
        except PrintError as e:
            click.echo(f"Print error: {e}", err=True)
            sys.exit(1)
        except PrinterError as e:
            click.echo(f"Printer error: {e}", err=True)
            sys.exit(1)
        finally:
            await printer.disconnect()

    asyncio.run(_test())


@main.command()
@click.argument("hex_data")
@click.option(
    "--address",
    "-a",
    callback=validate_bluetooth_address,
    help="Printer Bluetooth address (if omitted, scans and prompts)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Acknowledge security risks and skip warning prompt",
)
@click.pass_context
def raw(ctx, hex_data, address, force):
    """Send raw hex data to printer (for debugging/testing).

    WARNING: This command bypasses all safety checks and can potentially
    misconfigure or damage your printer. Only use if you understand TSPL
    protocol commands.

    If no address is specified, scans for printers and prompts for selection.
    """
    if not force:
        click.echo(
            "WARNING: Raw mode bypasses all safety checks and sends arbitrary "
            "data directly to the printer. This can potentially misconfigure "
            "or damage your printer.",
            err=True,
        )
        if not click.confirm("Do you want to continue?"):
            click.echo("Aborted.")
            return

    async def _raw():
        nonlocal address
        if address is None:
            address = await scan_and_select()
            if address is None:
                sys.exit(1)

        printer = P31SPrinter()
        printer.set_debug(True)  # Always debug for raw commands

        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            click.echo("Invalid hex data!", err=True)
            sys.exit(1)

        click.echo(f"Connecting to {address}...")

        if not await printer.connect(address):
            click.echo("Failed to connect!", err=True)
            sys.exit(1)

        try:
            click.echo(f"Sending: {data.hex()}")
            response = await printer.send_raw(data)

            if response:
                click.echo(f"Response: {response.hex()}")
            else:
                click.echo("No response")
        finally:
            await printer.disconnect()

    asyncio.run(_raw())


@main.command()
@click.argument("data")
@click.option(
    "--address",
    "-a",
    callback=validate_bluetooth_address,
    help="Printer Bluetooth address (if omitted, scans and prompts)",
)
@click.option(
    "--type",
    "barcode_type",
    type=click.Choice(["code128", "code39", "ean13", "upca"]),
    default="code128",
    help="Barcode type (default: code128)",
)
@click.option(
    "--density",
    type=click.IntRange(0, 15),
    default=8,
    help="Print density (0-15, default 8)",
)
@click.option("--copies", default=1, help="Number of copies")
@click.option("--no-text", is_flag=True, help="Omit human-readable text below barcode")
@click.option("--retry", default=0, help="Number of retries for transient failures")
@click.pass_context
def barcode(ctx, data, address, barcode_type, density, copies, no_text, retry):
    """Generate and print a barcode.

    DATA is the content to encode (numbers/text depending on barcode type).

    If no address is specified, scans for printers and prompts for selection.

    Examples:
        p31s barcode "12345"
        p31s barcode "HELLO" --type code39
        p31s barcode "12345" -a AA:BB:CC:DD:EE:FF
    """

    async def _barcode():
        nonlocal address
        if address is None:
            address = await scan_and_select()
            if address is None:
                sys.exit(1)

        try:
            click.echo(f"Generating {barcode_type} barcode...")
            img = generate_barcode(
                data,
                barcode_type=barcode_type,
                include_text=not no_text,
            )
        except ImportError as e:
            click.echo(str(e), err=True)
            sys.exit(1)
        except ValueError as e:
            click.echo(f"Invalid barcode data: {e}", err=True)
            sys.exit(1)

        printer = P31SPrinter()
        printer.set_debug(ctx.obj["debug"])

        click.echo(f"Connecting to {address}...")

        try:
            if not await printer.connect(address, retries=retry):
                click.echo("Failed to connect!", err=True)
                sys.exit(1)

            click.echo("Printing barcode...")
            success = await printer.print_image(
                img,
                density=Density(density),
                copies=copies,
                retries=retry,
            )

            if success:
                click.echo("Barcode printed!")
            else:
                click.echo("Print failed!", err=True)
                sys.exit(1)

        except ConnectionError as e:
            click.echo(f"Connection error: {e}", err=True)
            sys.exit(1)
        except PrintError as e:
            click.echo(f"Print error: {e}", err=True)
            sys.exit(1)
        except PrinterError as e:
            click.echo(f"Printer error: {e}", err=True)
            sys.exit(1)
        finally:
            await printer.disconnect()

    asyncio.run(_barcode())


@main.command()
@click.argument("data")
@click.option(
    "--address",
    "-a",
    callback=validate_bluetooth_address,
    help="Printer Bluetooth address (if omitted, scans and prompts)",
)
@click.option(
    "--size",
    type=click.Choice(["small", "medium", "large"]),
    default="medium",
    help="QR code size (default: medium)",
)
@click.option(
    "--error-correction",
    type=click.Choice(["L", "M", "Q", "H"]),
    default="M",
    help="Error correction level (L=7%%, M=15%%, Q=25%%, H=30%%)",
)
@click.option(
    "--density",
    type=click.IntRange(0, 15),
    default=8,
    help="Print density (0-15, default 8)",
)
@click.option("--copies", default=1, help="Number of copies")
@click.option("--retry", default=0, help="Number of retries for transient failures")
@click.pass_context
def qr(ctx, data, address, size, error_correction, density, copies, retry):
    """Generate and print a QR code.

    DATA is the content to encode (URL, text, etc.).

    If no address is specified, scans for printers and prompts for selection.

    Examples:
        p31s qr "https://example.com"
        p31s qr "Hello World" --size large
        p31s qr "https://example.com" -a AA:BB:CC:DD:EE:FF
    """

    async def _qr():
        nonlocal address
        if address is None:
            address = await scan_and_select()
            if address is None:
                sys.exit(1)

        try:
            click.echo(f"Generating QR code ({size})...")
            img = generate_qr(
                data,
                size=size,
                error_correction=error_correction,
            )
        except ImportError as e:
            click.echo(str(e), err=True)
            sys.exit(1)
        except ValueError as e:
            click.echo(f"Invalid QR data: {e}", err=True)
            sys.exit(1)

        printer = P31SPrinter()
        printer.set_debug(ctx.obj["debug"])

        click.echo(f"Connecting to {address}...")

        try:
            if not await printer.connect(address, retries=retry):
                click.echo("Failed to connect!", err=True)
                sys.exit(1)

            click.echo("Printing QR code...")
            success = await printer.print_image(
                img,
                density=Density(density),
                copies=copies,
                retries=retry,
            )

            if success:
                click.echo("QR code printed!")
            else:
                click.echo("Print failed!", err=True)
                sys.exit(1)

        except ConnectionError as e:
            click.echo(f"Connection error: {e}", err=True)
            sys.exit(1)
        except PrintError as e:
            click.echo(f"Print error: {e}", err=True)
            sys.exit(1)
        except PrinterError as e:
            click.echo(f"Printer error: {e}", err=True)
            sys.exit(1)
        finally:
            await printer.disconnect()

    asyncio.run(_qr())


@main.command("test-coverage")
@click.option(
    "--address",
    "-a",
    callback=validate_bluetooth_address,
    help="Printer Bluetooth address (if omitted, scans and prompts)",
)
@click.option("--width", default=96, help="Test pattern width in pixels")
@click.option("--height", default=304, help="Test pattern height in pixels")
@click.option("--x-offset", default=0, help="X offset in pixels")
@click.option("--y-offset", default=8, help="Y offset in pixels")
@click.option(
    "--density",
    type=click.IntRange(0, 15),
    default=10,
    help="Print density (0-15, default 10)",
)
@click.option("--retry", default=0, help="Number of retries for transient failures")
@click.pass_context
def test_coverage(ctx, address, width, height, x_offset, y_offset, density, retry):
    """Print a coverage test pattern to validate print area.

    Prints a pattern with border, corner markers, center crosshair,
    and grid ticks to verify the printable area boundaries.

    If no address is specified, scans for printers and prompts for selection.

    Examples:
        p31s test-coverage
        p31s test-coverage --width 100 --height 310
        p31s test-coverage -a AA:BB:CC:DD:EE:FF --x-offset 4 --y-offset 0
    """

    async def _test_coverage():
        nonlocal address
        if address is None:
            address = await scan_and_select()
            if address is None:
                sys.exit(1)

        click.echo(f"Generating coverage pattern ({width}x{height} px)...")
        pattern = generate_coverage_pattern(width=width, height=height)

        printer = P31SPrinter()
        printer.set_debug(ctx.obj["debug"])

        click.echo(f"Connecting to {address}...")

        try:
            if not await printer.connect(address, retries=retry):
                click.echo("Failed to connect!", err=True)
                sys.exit(1)

            click.echo(
                f"Printing coverage pattern (x={x_offset}, y={y_offset}, "
                f"density={density})..."
            )
            success = await printer.print_image(
                pattern,
                density=Density(density),
                x=x_offset,
                y=y_offset,
                retries=retry,
            )

            if success:
                click.echo("Coverage pattern printed!")
                click.echo("\nVerify:")
                click.echo("  - Border visible on all 4 edges (no clipping)")
                click.echo("  - Corner markers at label corners")
                click.echo("  - Center crosshair well-centered")
            else:
                click.echo("Print failed!", err=True)
                sys.exit(1)

        except ConnectionError as e:
            click.echo(f"Connection error: {e}", err=True)
            sys.exit(1)
        except PrintError as e:
            click.echo(f"Print error: {e}", err=True)
            sys.exit(1)
        except PrinterError as e:
            click.echo(f"Printer error: {e}", err=True)
            sys.exit(1)
        finally:
            await printer.disconnect()

    asyncio.run(_test_coverage())


if __name__ == "__main__":
    main()
