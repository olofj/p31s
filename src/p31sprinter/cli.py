"""
Command-Line Interface for P31S Printer.

Usage:
    p31 scan              - Scan for printers
    p31 discover ADDRESS  - Discover services on a printer
    p31 print ADDRESS IMAGE - Print an image
    p31 test ADDRESS      - Print test pattern
"""

import asyncio
import sys

import click

from .printer import (
    P31SPrinter,
    PrinterError,
    ConnectionError,
    PrintError,
    ImageError,
)
from .tspl import Density


@click.group()
@click.option("--debug/--no-debug", default=False, help="Enable debug output")
@click.pass_context
def main(ctx, debug):
    """P31S Label Printer CLI."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


@main.command()
@click.option("--timeout", default=10.0, help="Scan timeout in seconds")
def scan(timeout):
    """Scan for P31S printers."""

    async def _scan():
        click.echo(f"Scanning for printers ({timeout}s)...")
        printers = await P31SPrinter.scan(timeout=timeout)

        if not printers:
            click.echo("No printers found.")
            return

        click.echo(f"\nFound {len(printers)} printer(s):\n")
        for p in printers:
            click.echo(f"  {p}")

    asyncio.run(_scan())


@main.command()
@click.argument("address")
@click.pass_context
def discover(ctx, address):
    """Discover GATT services on a printer."""

    async def _discover():
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
@click.argument("address")
@click.argument("image", type=click.Path(exists=True))
@click.option(
    "--density",
    type=click.IntRange(0, 15),
    default=8,
    help="Print density (0-15, default 8)",
)
@click.option("--copies", default=1, help="Number of copies")
@click.option("--retry", default=0, help="Number of retries for transient failures")
@click.pass_context
def print_image(ctx, address, image, density, copies, retry):
    """Print an image file."""

    async def _print():
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
@click.argument("address")
@click.option("--retry", default=0, help="Number of retries for transient failures")
@click.pass_context
def test(ctx, address, retry):
    """Print a test pattern."""

    async def _test():
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
@click.argument("address")
@click.argument("hex_data")
@click.pass_context
def raw(ctx, address, hex_data):
    """Send raw hex data to printer (for testing)."""

    async def _raw():
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


if __name__ == "__main__":
    main()
