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

from .commands import LabelType, PrintDensity
from .printer import P31Printer


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
        printers = await P31Printer.scan(timeout=timeout)

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
        printer = P31Printer()
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
    type=click.Choice(["light", "normal", "dark"]),
    default="normal",
    help="Print density",
)
@click.option(
    "--label-type",
    type=click.Choice(["gap", "black-mark", "continuous"]),
    default="gap",
    help="Label media type",
)
@click.option("--copies", default=1, help="Number of copies")
@click.pass_context
def print_image(ctx, address, image, density, label_type, copies):
    """Print an image file."""
    density_map = {
        "light": PrintDensity.LIGHT,
        "normal": PrintDensity.NORMAL,
        "dark": PrintDensity.DARK,
    }
    label_map = {
        "gap": LabelType.GAP,
        "black-mark": LabelType.BLACK_MARK,
        "continuous": LabelType.CONTINUOUS,
    }

    async def _print():
        printer = P31Printer()
        printer.set_debug(ctx.obj["debug"])

        click.echo(f"Connecting to {address}...")

        if not await printer.connect(address):
            click.echo("Failed to connect!", err=True)
            sys.exit(1)

        try:
            click.echo(f"Printing {image}...")
            success = await printer.print_image(
                image,
                density=density_map[density],
                label_type=label_map[label_type],
                copies=copies,
            )

            if success:
                click.echo("Print complete!")
            else:
                click.echo("Print failed!", err=True)
                sys.exit(1)
        finally:
            await printer.disconnect()

    asyncio.run(_print())


@main.command()
@click.argument("address")
@click.pass_context
def test(ctx, address):
    """Print a test pattern."""

    async def _test():
        printer = P31Printer()
        printer.set_debug(ctx.obj["debug"])

        click.echo(f"Connecting to {address}...")

        if not await printer.connect(address):
            click.echo("Failed to connect!", err=True)
            sys.exit(1)

        try:
            click.echo("Printing test pattern...")
            success = await printer.print_test_pattern()

            if success:
                click.echo("Test print complete!")
            else:
                click.echo("Test print failed!", err=True)
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
        printer = P31Printer()
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
