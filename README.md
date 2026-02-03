# P31S Label Printer Driver

Open-source Linux/macOS driver for the **POLONO P31S** thermal label printer.

## About the P31S

The POLONO P31S is a compact, battery-powered thermal label printer designed for portable use. It prints on small 14×40mm adhesive label stickers, making it ideal for organizing cables, labeling storage containers, price tags, or any application requiring small durable labels.

Key hardware specs:
- **Print technology:** Direct thermal (no ink required)
- **Resolution:** 203 DPI
- **Label size:** 14×40mm (printable area: ~120×320 pixels)
- **Connectivity:** Bluetooth Low Energy (BLE)
- **Power:** Rechargeable battery
- **Price:** ~$20-30 USD

The printer uses a subset of the TSPL (TSC Printer Language) protocol over BLE, which this driver implements.

## Features

- Print images to 40x14mm labels at 203 DPI (120x320 pixels max)
- Query printer status, battery level, and firmware version
- Simple CLI and Python API
- Uses TSPL text commands over Bluetooth Low Energy

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .

# Or install dependencies only
pip install bleak pillow click
```

## Quick Start

### Scan for Printers

```bash
# Using CLI
p31s scan

# Or using the discovery tool
python tools/discover.py
```

### Discover Printer Services

```bash
# Get detailed GATT service info
python tools/discover.py --address XX:XX:XX:XX:XX:XX
```

### Print an Image

```bash
p31s print XX:XX:XX:XX:XX:XX image.png
p31s print XX:XX:XX:XX:XX:XX image.png --density 12 --copies 2
```

### Print Test Pattern

```bash
p31s test XX:XX:XX:XX:XX:XX
```

### Raw Command (Debugging Only)

The `raw` command sends arbitrary hex data directly to the printer for debugging purposes:

```bash
p31s raw XX:XX:XX:XX:XX:XX "1b21"
```

**⚠️ Security Warning:** This command bypasses all safety checks and can send arbitrary TSPL commands. Incorrect use may misconfigure or damage your printer. Use `--force` to skip the confirmation prompt:

```bash
p31s raw XX:XX:XX:XX:XX:XX "1b21" --force
```

## Library Usage

```python
import asyncio
from p31s import P31SPrinter

async def main():
    # Scan for printers
    printers = await P31SPrinter.scan()
    print(f"Found: {printers}")

    # Connect and print
    printer = P31SPrinter()
    if await printer.connect(printers[0].address):
        await printer.print_image("label.png")
        await printer.disconnect()

asyncio.run(main())
```

## Project Structure

```
p31/
├── src/p31s/      # Main library
│   ├── printer.py       # High-level API (P31SPrinter class)
│   ├── connection.py    # BLE connection (scan, chunked writes)
│   ├── tspl.py          # TSPL command builder
│   ├── tspl_commands.py # Status queries (CONFIG?, BATTERY?)
│   ├── responses.py     # Response parsers
│   └── cli.py           # Command-line interface
├── tools/               # Development utilities
│   └── discover.py      # BLE scanner/debugger
├── docs/
│   └── protocol.md      # Protocol documentation
└── tests/               # Unit tests
```

## Testing

### Unit Tests

Run unit tests (no hardware required):

```bash
# Install test dependencies
pip install -e ".[dev]"
pip install pytest-asyncio

# Run unit tests only
pytest tests/ -m "not hardware"
```

### Integration Tests (Hardware Required)

Integration tests require a real P31S printer connected via Bluetooth:

```bash
# First, find your printer's address
p31s scan

# Run all tests including hardware tests
pytest tests/ -m hardware --address=XX:XX:XX:XX:XX:XX

# Run specific test categories
pytest tests/test_integration.py -m hardware --address=XX:XX:XX:XX:XX:XX -k "TestConnection"
pytest tests/test_integration.py -m hardware --address=XX:XX:XX:XX:XX:XX -k "TestPrint"
```

**Warning:** Print tests (`TestPrint`) will actually print labels. Make sure you have paper loaded.

## Protocol Documentation

See [docs/protocol.md](docs/protocol.md) for the complete protocol specification.

## Dependencies

- **bleak** - Bluetooth Low Energy library
- **pillow** - Image processing
- **click** - CLI framework

## Bluetooth Permissions

### Linux

```bash
# Add user to bluetooth group
sudo usermod -aG bluetooth $USER
# Log out and back in

# Or run with sudo for testing
sudo python tools/discover.py
```

### macOS

Grant Bluetooth access when prompted by the system.

## References

- [TSPL Programming Manual](https://www.tscprinters.com/EN/support/support_download/TSPL_TSPL2_Programming.pdf)

## License

Apache 2.0 - see [LICENSE](LICENSE)
