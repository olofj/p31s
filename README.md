# P31 Label Printer Driver

Linux/macOS driver for the **POLONO P31S** thermal label printer.

> **Status:** Protocol reverse engineering in progress

## Overview

This project aims to reverse engineer and document the BLE protocol used by the P31S label printer, then provide an open-source driver for Linux and macOS.

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
p31 scan

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
p31 print XX:XX:XX:XX:XX:XX image.png
p31 print XX:XX:XX:XX:XX:XX image.png --density dark --copies 2
```

### Print Test Pattern

```bash
p31 test XX:XX:XX:XX:XX:XX
```

## Protocol Reverse Engineering

### Tools Provided

1. **discover.py** - Scan for printers and dump GATT services
2. **test_protocols.py** - Test known protocols (NIIMBOT, Cat Printer, ESC/POS)
3. **apk_uuid_finder.py** - Extract UUIDs from decompiled APK

### APK Analysis

```bash
# Download Labelnize APK from APKPure
# Decompile with JADX
./jadx/bin/jadx -d labelnize_decompiled labelnize.apk

# Search for protocol info
python tools/apk_uuid_finder.py labelnize_decompiled
```

### Protocol Testing

```bash
# Test various protocols against the printer
python tools/test_protocols.py XX:XX:XX:XX:XX:XX
```

## Library Usage

```python
import asyncio
from p31printer import P31Printer

async def main():
    # Scan for printers
    printers = await P31Printer.scan()
    print(f"Found: {printers}")

    # Connect and print
    printer = P31Printer()
    if await printer.connect(printers[0].address):
        await printer.print_image("label.png")
        await printer.disconnect()

asyncio.run(main())
```

## Project Structure

```
p31/
├── src/p31printer/      # Main library
│   ├── protocol.py      # Packet encoding/decoding
│   ├── commands.py      # Command definitions
│   ├── connection.py    # BLE connection handling
│   ├── printer.py       # High-level API
│   ├── image.py         # Image processing
│   └── cli.py           # Command-line interface
├── tools/               # Reverse engineering tools
│   ├── discover.py      # BLE scanner
│   ├── test_protocols.py # Protocol tester
│   └── apk_uuid_finder.py # APK analysis
├── docs/
│   └── protocol.md      # Protocol documentation
└── tests/               # Unit tests
```

## Protocol Documentation

See [docs/protocol.md](docs/protocol.md) for the work-in-progress protocol specification.

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

## Help Wanted

This project needs contributors with access to P31S hardware. Here's how you can help:

### High Priority

- **Hardware Testing** - Run `python tools/discover.py -a <ADDRESS>` and share the GATT service/characteristic UUIDs from your P31S
- **Protocol Verification** - Test whether TSPL commands or binary protocol works with your printer using `python tools/test_protocols.py <ADDRESS>`
- **Print Testing** - Try printing with `p31 test <ADDRESS>` and report results

### Medium Priority

- **Other Printer Models** - Test compatibility with similar printers (NIIMBOT, MakeID, Phomemo)
- **macOS Testing** - Verify the driver works correctly on macOS
- **Label Size Calibration** - Help determine correct DPI and margin settings for various label sizes

### Nice to Have

- **QuickLZ Compression** - Implement bitmap compression for faster printing (used by the official app)
- **Label Templates** - Add support for common label layouts (address labels, barcodes, etc.)
- **Windows Support** - Test and fix any Windows-specific issues with Bleak
- **Documentation** - Improve protocol documentation based on testing findings

### How to Contribute

1. Open an issue with your findings (device info, working/non-working commands)
2. Submit PRs for bug fixes or new features
3. Share Bluetooth packet captures if you can obtain them

## References

- [NIIMBOT Protocol Wiki](https://printers.niim.blue/interfacing/proto/)
- [Cat Printer Reverse Engineering](https://werwolv.net/blog/cat_printer)
- [Phomemo D30 Protocol](https://github.com/polskafan/phomemo_d30)
- [TSPL Programming Manual](https://www.tscprinters.com/EN/support/support_download/TSPL_TSPL2_Programming.pdf)

## License

MIT
