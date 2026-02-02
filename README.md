# P31S Label Printer Driver

Open-source Linux/macOS driver for the **POLONO P31S** thermal label printer.

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

## Library Usage

```python
import asyncio
from p31sprinter import P31SPrinter

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
├── src/p31sprinter/      # Main library
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

## Contributing

Contributions welcome! Some ideas:

- **QuickLZ Compression** - Faster bitmap transfers
- **Barcode/QR Support** - Using TSPL's built-in commands
- **Windows Testing** - Verify Bleak compatibility
- **Other Label Sizes** - Calibration for different dimensions

## References

- [TSPL Programming Manual](https://www.tscprinters.com/EN/support/support_download/TSPL_TSPL2_Programming.pdf)
- [NIIMBOT Protocol Wiki](https://printers.niim.blue/interfacing/proto/)

## License

Apache 2.0 - see [LICENSE](LICENSE)
