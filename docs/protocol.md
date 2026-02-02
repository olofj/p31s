# P31S Printer Protocol Documentation

> **Status:** Active Research - Protocol reverse engineering in progress

## Overview

The POLONO P31S is a 203 DPI thermal label printer that communicates via Bluetooth Low Energy (BLE).

## BLE Communication

### Device Discovery

The printer advertises with names matching patterns:
- `P31S`
- `POLONO`
- `MAKEID`
- `NIIMBOT`
- `LABEL`

### GATT Services (Discovered from Labelnize APK)

**Primary Service:**
- **Service UUID:** `0000ff00-0000-1000-8000-00805f9b34fb` (0xFF00)

**Characteristics:**
| Name | UUID | Properties | Purpose |
|------|------|------------|---------|
| Read | `0000ff01-0000-1000-8000-00805f9b34fb` | Read | Read data from printer |
| Write | `0000ff02-0000-1000-8000-00805f9b34fb` | Write, Write No Response | Send commands to printer |
| Notify | `0000ff03-0000-1000-8000-00805f9b34fb` | Notify | Receive async responses |

**Alternative UUIDs (from other similar printers):**
- `0000ae00-0000-1000-8000-00805f9b34fb` - Service
- `0000ae01-0000-1000-8000-00805f9b34fb` - Write characteristic
- `0000ae02-0000-1000-8000-00805f9b34fb` - Notify characteristic
- `49535343-fe7d-4ae5-8fa9-9fafd205e455` - Microchip UART Service

### MTU

The app requests MTU of 512 bytes after service discovery.

## Command Protocol

The Labelnize app uses multiple protocols depending on the printer model:
1. **TSPL (TSC Printer Language)** - Text-based commands for label printers
2. **ESC/POS** - Standard thermal printer commands
3. **Custom Binary Protocol** - For specific printer models

**Key Discovery:** The P31S uses TSPL text-based commands, NOT the NIIMBOT binary protocol.

### Status Query Commands (from O8.java)

These text-based commands query printer status:

| Command | Purpose | CMD_TYPE |
|---------|---------|----------|
| `CONFIG?\r\n` | Query firmware/hardware version, resolution, settings | 10 |
| `BATTERY?\r\n` | Query battery level and charging status | 13 |
| `SELFTEST\r\n` | Trigger self-test print | 12 |
| `INITIALPRINTER\r\n` | Initialize printer | 11 |
| `GETCHUNKSIZE\r\n` | Query supported chunk size | 16 |
| `GETPRINTEDCOUNT\r\n` | Query print counter | 35 |

#### CONFIG? Response (from PrinterConfig.java)

Response is 19 or 20 bytes:

```
Offset  Length  Field
0-6     7       Header (unknown format, stripped before parsing)
7-8     2       Resolution (little-endian uint16, e.g., 203 DPI)
9-11    3       Hardware version (3 bytes -> hex string like "010203")
12-14   3       Firmware version (3 bytes -> hex string like "010203")
15      1       Shutdown timer setting
16      1       Sound setting (0=off, 1=on)
17      1       Config version (only in 20-byte response)
18-19   2       CRLF terminator (\r\n)
```

**Version Format:** Each byte represents a version component.
- `01 02 03` = Version 1.2.3

#### BATTERY? Response

Response is 11 or 12 bytes:

```
Offset  Length  Field
0-6     7       "BATTERY" ASCII header
7       1       Battery level (BCD) - 11-byte response
        OR      Charging status (1=charging) - 12-byte response
8       1       Battery level (BCD) - 12-byte response only
-2,-1   2       CRLF terminator (\r\n)
```

**BCD Encoding:** Battery level is Binary-Coded Decimal.
- `0x50` = 50%
- `0x99` = 99%

### TSPL Commands (Primary for label printers)

TSPL is a text-based command language. Commands are sent as ASCII strings terminated with `\r\n` (CRLF).

**Common Commands:**
```
SIZE 15 mm,10 mm      # Set label size
GAP 2 mm,0 mm         # Set gap between labels
CLS                   # Clear image buffer
DENSITY 8             # Set print density (0-15)
DIRECTION 0,0         # Set print direction
BITMAP x,y,w,h,mode,data  # Print bitmap
PRINT 1               # Print 1 copy
```

**Bitmap Command Format:**
```
BITMAP x,y,width_bytes,height,mode,<binary_data>
```
- `x, y`: Position in dots
- `width_bytes`: Width in bytes (8 pixels per byte)
- `height`: Height in dots
- `mode`: 0=overwrite, 1=OR, 2=XOR, 3=QuickLZ compressed

### Binary Packet Format (NIIMBOT-style)

For printers using binary protocol:

```
+------+------+---------+----------+------+----------+------+------+
| 0x55 | 0x55 | Command | Data Len | Data | Checksum | 0xAA | 0xAA |
+------+------+---------+----------+------+----------+------+------+
  Head          CMD        LEN       ...      XOR        Tail
```

**Checksum:** XOR of all bytes from Command through Data

### ESC/POS Commands

Standard thermal printer commands:
- `ESC @` (0x1B 0x40) - Initialize printer
- `GS v 0` (0x1D 0x76 0x30) - Print raster bit image
- `ESC !` (0x1B 0x21) - Select print mode

## Image Format

### Bitmap Encoding

- **Resolution:** 203 DPI
- **Maximum Width:** ~15mm (approximately 120 pixels)
- **Bit Order:** MSB first
- **Color:**
  - For TSPL: 1 = white (no burn), 0 = black (burn)
  - For some binary protocols: 1 = black (burn), 0 = white

### Compression

The app supports QuickLZ compression for bitmap data:
- Mode 3 in BITMAP command indicates compressed data
- Reduces data transfer size significantly for large images

## Print Job Sequence

### TSPL Sequence

```
1. SIZE 15 mm,10 mm\r\n    # Set label dimensions
2. GAP 2 mm,0 mm\r\n       # Set gap (or BLINE for black mark)
3. CLS\r\n                 # Clear buffer
4. DENSITY 8\r\n           # Set density
5. BITMAP x,y,w,h,0,<data> # Send image
6. PRINT 1\r\n             # Print
```

### Binary Protocol Sequence

```
1. Connect command (0xC1)
2. Set label type
3. Set density
4. Set page size
5. Print start (0x01)
6. Send bitmap rows
7. Page end (0xE3)
8. Print end (0xF3)
```

## Printer Status Codes

From `YXPrinterConstant.java`:

| Status | Code | Description |
|--------|------|-------------|
| OK | 461200 | Normal operation |
| Cover Open | 461201 | Printer cover is open |
| No Paper | 461202 | Out of paper |
| No Power | 461203 | Low battery |
| Overheat | 461204 | Thermal head overheated |

## Paper Types

| Type | Description |
|------|-------------|
| Black Mark | Labels with black marks for positioning |
| Continuous | Continuous roll (no gaps) |
| Gap/Label | Labels with gaps between them |
| Tattoo | Special tattoo paper |

## References

- [TSPL/TSPL2 Programming Manual](https://www.tscprinters.com/EN/support/support_download/TSPL_TSPL2_Programming.pdf)
- [ESC/POS Command Reference](https://reference.epson-biz.com/modules/ref_escpos/index.php)
- [NIIMBOT Protocol Wiki](https://printers.niim.blue/interfacing/proto/)

---

## APK Analysis Notes

### Decompiled Files of Interest

- `com/printer/psdk/device/bluetooth/ble/ConnectionImplBle.java` - BLE connection handling
- `com/print/android/base_lib/cmd/LabelCommand.java` - TSPL command generation
- `com/print/android/base_lib/cmd/EscCommand.java` - ESC/POS command generation
- `com/ezink/data/constant/YXPrinterConstant.java` - Status codes and constants

### Key Findings

1. The app uses standard GATT service `0000ff00` with characteristics `ff01`, `ff02`, `ff03`
2. Primary command protocol is TSPL (text-based)
3. Bitmap data can be optionally compressed with QuickLZ
4. The app supports multiple printer models with different protocols

---

## Verification Log

### APK Analysis
- [x] Downloaded Labelnize APK from APKPure
- [x] Decompiled with JADX
- [x] Extracted GATT UUIDs
- [x] Identified command protocols (TSPL, ESC/POS)
- [x] Found status code definitions

### Live Testing
- [ ] Run discover.py against actual P31S printer
- [ ] Confirm service/characteristic UUIDs
- [ ] Test TSPL commands
- [ ] Test binary protocol commands

---

## Protocol Comparison

| Aspect | Binary (NIIMBOT) | Text (TSPL) |
|--------|-----------------|-------------|
| Format | Binary with 55 55 header | ASCII text with CRLF |
| Version query | `0x40` command code | `CONFIG?\r\n` text |
| Battery query | `0xDC` heartbeat | `BATTERY?\r\n` text |
| Checksum | XOR of payload | None (plain text) |
| Used by | NIIMBOT D-series | POLONO P31S |

**Note:** The P31S may respond to both protocols depending on context. Use `test_status_commands.py` to verify which protocol is active.
