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

#### CONFIG? Response (verified from hardware)

Response is 19 bytes:

```
Offset  Length  Field
0-6     7       "CONFIG " header (including trailing space)
7       1       Padding (0x00)
8       1       Resolution (single byte, e.g., 0xCB = 203 DPI)
9       1       Padding (0x00)
10-12   3       Hardware version (3 bytes, e.g., [0x00, 0x01, 0x00] = 0.1.0)
13-15   3       Firmware version (3 bytes, e.g., [0x01, 0x04, 0x02] = 1.4.2)
16      1       Settings byte
17-18   2       CRLF terminator (\r\n)
```

**Example Response:**
```
434f4e4649472000cb00000100010402000d0a
"CONFIG " 00 CB 00 | 00 01 00 | 01 04 02 | 00 | \r\n
          ^res     ^hw 0.1.0  ^fw 1.4.2  ^settings
```

#### BATTERY? Response (verified from hardware)

Response is 12 bytes:

```
Offset  Length  Field
0-7     8       "BATTERY " header (including trailing space)
8       1       Battery level (BCD encoded)
9       1       Charging status (0=not charging, 1=charging)
10-11   2       CRLF terminator (\r\n)
```

**Example Response:**
```
424154544552592075000d0a
"BATTERY " 75 00 \r\n
           ^75% ^not charging
```

**BCD Encoding:** Battery level is Binary-Coded Decimal.
- `0x50` = 50%
- `0x75` = 75%
- `0x99` = 99%

### TSPL Commands (Primary for label printers)

TSPL is a text-based command language. Commands are sent as ASCII strings terminated with `\r\n` (CRLF).

**Print Job Command Sequence (from LabelCommand.java):**
```
SIZE 15 mm,12 mm       # Set label size
GAP 2 mm,0 mm          # Set gap between labels
DIRECTION 0,0          # Set print direction (0=normal, 1=180°)
DENSITY 8              # Set print density (0-15, skip if -1)
CLS                    # Clear image buffer
BITMAP x,y,w,h,0,data  # Send bitmap with binary data
PRINT 1                # Print 1 copy
```

**Important:** The command sequence matters. The APK always sends commands in this order:
1. SIZE
2. GAP
3. DIRECTION
4. DENSITY (optional)
5. CLS
6. BITMAP
7. PRINT

**Bitmap Command Format:**
```
BITMAP x,y,width_bytes,height,mode,<binary_data>\r\n
```
- `x, y`: Position in dots (203 dots per inch)
- `width_bytes`: Width in bytes (pixels / 8, rounded up)
- `height`: Height in dots
- `mode`: 0=overwrite, 1=OR, 2=XOR, 3=QuickLZ compressed
- `<binary_data>`: Raw bitmap data immediately after comma, followed by CRLF

**Bitmap Data Format:**
- 1-bit per pixel, MSB first (leftmost pixel in high bit)
- For TSPL: 0 = black (burn), 1 = white (no burn)
- Data length = width_bytes × height bytes

**Other Commands:**
```
BAR x,y,width,height   # Draw filled rectangle (may not work on all printers)
BLINE n mm,0 mm        # Set black mark detection
OFFSET n mm            # Set offset
FORMFEED               # Feed to next label
SOUND n,t              # Play beep (n times, t duration)
```

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
1. SIZE 14 mm,40 mm\r\n    # Set label dimensions (width=14mm, height=40mm)
2. GAP 2 mm,0 mm\r\n       # Set gap (or BLINE for black mark)
3. DIRECTION 0,0\r\n       # Set print direction
4. DENSITY 8\r\n           # Set density (0-15)
5. CLS\r\n                 # Clear buffer
6. BITMAP x,y,w,h,1,<data> # Send image (mode 1=OR works best)
7. PRINT 1\r\n             # Print
```

### Binary Protocol Sequence (NOT WORKING)

Note: The NIIMBOT-style binary protocol was explored but does not work with the P31S.
The printer uses TSPL text commands instead.

```
1. Connect command (0xC1)  # Does not work
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

## P31S Device Configuration (from cloud_config_labelnize.json)

The P31S printer is configured with these parameters:

```json
{
  "deviceName": "P31S",
  "command": 0,           // isPrintModelAfterSend - standard TSPL
  "dpi": 203,             // 203 dots per inch
  "maxWidth": 12,         // 12mm maximum print width
  "isEncrypt": 1,         // Paper encryption enabled (RFID)
  "isHalfInch": 1,        // Half-inch device mode
  "paperType": "0,1",     // Supports gap (0) and continuous (1)
  "defaultGap": 5,        // Default 5mm gap
  "defaultTemplateWidth": 40,
  "defaultTemplateHeight": 14,
  "densityModel": 0,      // Manual density control
  "compressionType": -1,  // No compression
  "canEnergy": 1,         // Battery monitoring supported
  "canSet": 1,            // Settings adjustable
  "upgradeType": 1        // JieLi firmware upgrade method
}
```

**Command Types (from Devices.java):**
| Type | Name | Description |
|------|------|-------------|
| 0 | isPrintModelAfterSend | Standard TSPL - print after all data sent |
| 1 | isFakeESCCommand | ESC-like but different |
| 2 | isPrintModelESCCommand | Standard ESC/POS |
| 3 | isPrintModelPl70e | PL70e specific protocol |
| 4 | isYXCommand | YinXiang protocol |
| 5 | isAYCommand | AY protocol |
| 6 | isPocketCommand | Pocket printer protocol |
| 7 | isPrintModelSpecial | Special TSPL variant |
| 8 | isYXTwoInchCommand | YinXiang 2-inch |
| 9 | isYXFourInchCommand | YinXiang 4-inch |

**P31S uses command type 0**, which means:
- Standard TSPL text commands
- All commands sent as ASCII with CRLF terminator
- Print executes after PRINT command is sent
- No special handshaking required (but RFID read may be needed for paper verification)

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

---

## iOS BLE Capture Analysis

Analysis of actual iOS app (Labelnize) traffic via sysdiagnose BLE packet capture.

### Connection Parameters

- **MTU**: Client requests 527, server responds with 124
- **Effective chunk size**: ~121 bytes (MTU - 3 for ATT overhead)

### GATT Handles

| Handle | Purpose |
|--------|---------|
| 0x0006 | Write commands (TSPL text) |
| 0x0008 | Receive notifications (responses) |
| 0x0012 | Write (encryption/authentication related) |
| 0x0015 | Write (encryption/authentication - 48-byte blocks) |
| 0x0020 | Write (encryption/authentication related) |

### Working Print Sequence (from capture)

```
SIZE 15 mm,40 mm\r\n
GAP 5.0 mm,0 mm\r\n
DIRECTION 0,0\r\n
DENSITY 15\r\n
CLS\r\n
BITMAP 0,8,12,304,1,<binary_data>\r\n
PRINT 1\r\n
```

Key observations:
- **BITMAP mode 1 (OR)** is used, not mode 0 (OVERWRITE)
- **Density 15** (maximum) is used
- Large bitmap data is chunked across multiple BLE writes
- CRLF terminator appears at the END of all bitmap data, not after the command prefix
- Commands sent via Write Without Response (ATT opcode 0x52)

### Thermal Protection

The P31S rejects bitmap data that is entirely 0x00 (solid black). This is thermal head protection to prevent overheating.

**Working patterns:**
- Checkerboard (0xAA/0x55) - alternating pixels
- Gradient (0x80, 0xC0, 0xE0, etc.) - varying coverage
- Any pattern with at least some 1-bits per region

**Failing patterns:**
- Solid black (all 0x00 bytes) - rejected silently

**Workaround:** Use dithered black (e.g., alternate 0x00 with 0x08) to achieve near-black appearance while satisfying thermal protection requirements.
