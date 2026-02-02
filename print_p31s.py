#!/usr/bin/env python3
"""
P31S Printer Protocol Implementation

Based on Labelnize APK analysis:
- Uses Classic Bluetooth SPP (RFCOMM) only
- BITMAP_SN protocol with sequence numbers and XOR checksums
- LZO compression on bitmap data
- 1024-byte chunks with state machine for reliable delivery

Protocol format:
  BITMAP_SN x,y,width,height,quality,bitmapModel,dataLength,numPackets,chunkSize,
  [SN_HIGH][SN_LOW][COMPRESSED_DATA...][XOR]
  ...
  [LAST_CHUNK]\r\n

Where:
- quality: 0=FAST, 2=PHOTO
- bitmapModel: 4=JPEG, 5=PNG, 6=BMP, 8=GRAY
- chunkSize: 8192 (in header), actual data chunk is 8189 bytes
- Each chunk has 2-byte sequence number prefix and 1-byte XOR suffix
"""

import io
import time
import serial
from PIL import Image

# Try to import LZO compression
try:
    import lzo
    HAS_LZO = True
except ImportError:
    HAS_LZO = False
    print("Warning: python-lzo not installed. Install with: pip install python-lzo")
    print("Will try without compression first.\n")


SERIAL_PORT = "/dev/cu.P31S"
BAUD_RATE = 115200

# Protocol constants
CHUNK_DATA_SIZE = 8189  # Max data bytes per chunk
CHUNK_SIZE_HEADER = 8192  # Value in header
CHUNK_WRITE_SIZE = 1024  # Actual write chunk size to serial
CRLF = b"\r\n"


def build_chunks_with_sn_xor(data: bytes, chunk_size: int = CHUNK_DATA_SIZE) -> list[bytes]:
    """Build data chunks with sequence number and XOR checksum."""
    chunks = []
    num_chunks = (len(data) + chunk_size - 1) // chunk_size

    for i in range(num_chunks):
        start = i * chunk_size
        end = min(start + chunk_size, len(data))
        chunk_data = data[start:end]

        # Build packet: [SN_HIGH][SN_LOW][DATA...][XOR]
        sn_high = (i >> 8) & 0xFF
        sn_low = i & 0xFF

        # XOR checksum of data only
        xor = 0
        for b in chunk_data:
            xor ^= b

        packet = bytes([sn_high, sn_low]) + chunk_data + bytes([xor])
        chunks.append(packet)

    return chunks


def compress_data(data: bytes) -> bytes:
    """Compress data using LZO if available."""
    if HAS_LZO:
        compressed = lzo.compress(data, 1)  # Level 1 compression
        print(f"  LZO compressed: {len(data)} -> {len(compressed)} bytes")
        return compressed
    return data


def create_test_image(width: int = 120, height: int = 30) -> bytes:
    """Create a simple test image and return as JPEG bytes."""
    img = Image.new('RGB', (width, height), 'white')
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([5, 5, 25, 25], fill='black')
    draw.text((35, 8), "P31S", fill='black')

    # Rotate 180 degrees (as the APK does)
    img = img.rotate(180)

    # Convert to JPEG with quality 60 (as the APK does)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=60)
    return buf.getvalue()


def send_chunked(ser: serial.Serial, data: bytes, chunk_size: int = CHUNK_WRITE_SIZE, delay: float = 0.001):
    """Send data in chunks with small delays."""
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        ser.write(chunk)
        if delay > 0:
            time.sleep(delay)
    ser.flush()


def wait_for_response(ser: serial.Serial, timeout: float = 5.0) -> bytes | None:
    """Wait for response from printer."""
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            time.sleep(0.1)  # Wait a bit more for complete response
            return ser.read(ser.in_waiting)
        time.sleep(0.1)
    return None


def print_image(ser: serial.Serial, jpeg_data: bytes, width: int, height: int,
                x: int = 0, y: int = 0, quality: int = 0, use_compression: bool = True) -> bool:
    """
    Send image to printer using BITMAP_SN protocol.

    Args:
        ser: Serial connection
        jpeg_data: JPEG image bytes
        width: Image width in pixels
        height: Image height in pixels
        x, y: Position on label
        quality: 0=FAST, 2=PHOTO
        use_compression: Whether to use LZO compression

    Returns:
        True if successful
    """
    print(f"\nPrinting image: {width}x{height}, {len(jpeg_data)} bytes")

    # Optionally compress
    data_to_send = jpeg_data
    if use_compression and HAS_LZO:
        data_to_send = compress_data(jpeg_data)

    # Build chunks with sequence numbers and XOR
    chunks = build_chunks_with_sn_xor(data_to_send, CHUNK_DATA_SIZE)
    print(f"  Chunks: {len(chunks)}")

    # Build BITMAP_SN header
    bitmap_model = 4  # JPEG
    header = f"BITMAP_SN {x},{y},{width},{height},{quality},{bitmap_model},{len(data_to_send)},{len(chunks)},{CHUNK_SIZE_HEADER},"
    print(f"  Header: {header}")

    # Construct full packet
    if len(chunks) == 1:
        # Single chunk: header + chunk + CRLF
        packet = header.encode('ascii') + chunks[0] + CRLF
    else:
        # Multi-chunk: (header + chunk), (chunk)..., (chunk + CRLF)
        packet = header.encode('ascii') + chunks[0]
        for chunk in chunks[1:-1]:
            packet += chunk
        packet += chunks[-1] + CRLF

    print(f"  Total packet: {len(packet)} bytes")

    # Send
    print("  Sending...")
    send_chunked(ser, packet)

    # Wait for response
    print("  Waiting for response...")
    response = wait_for_response(ser, timeout=10.0)

    if response:
        print(f"  Response: {response.hex()}")
        # 0xAA = success
        if 0xAA in response:
            print("  SUCCESS! (0xAA received)")
            return True
        # Check for BITMAP_SN_RESEND
        if b"BITMAP_SN_RESEND" in response:
            print("  Printer requested resend!")
            # TODO: Implement resend logic
            return False
    else:
        print("  No response")

    return False


def query_status(ser: serial.Serial) -> int | None:
    """Query printer status. Returns status byte or None."""
    ser.reset_input_buffer()
    ser.write(bytes([0x1b, 0x21, 0x3f, 0x0d, 0x0a]))  # ESC ! ? \r\n
    ser.flush()

    response = wait_for_response(ser, timeout=2.0)
    if response:
        print(f"Status response: {response.hex()}")
        return response[0] if len(response) > 0 else None
    return None


def main():
    print("P31S Printer Test")
    print("=" * 60)

    # Check for LZO
    if not HAS_LZO:
        print("\nNote: LZO compression not available.")
        print("The printer may require compression. Install with:")
        print("  pip install python-lzo")
        print("\nContinuing without compression...\n")

    # Open serial port
    print(f"Opening {SERIAL_PORT}...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2, write_timeout=2)
        print("Connected!")
    except Exception as e:
        print(f"Failed to open serial port: {e}")
        print("\nMake sure:")
        print("  1. Printer is paired in System Settings > Bluetooth")
        print("  2. Printer is powered on")
        print("  3. /dev/cu.P31S exists")
        return

    try:
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.3)

        # Test 1: SELFTEST
        print("\n" + "=" * 60)
        print("Test 1: SELFTEST")
        print("=" * 60)
        ser.write(b"SELFTEST\r\n")
        ser.flush()
        time.sleep(3)
        if ser.in_waiting:
            resp = ser.read(ser.in_waiting)
            print(f"Response: {resp.hex()}")
        else:
            print("No response (check if selftest printed)")

        input("\nPress Enter to continue...")

        # Test 2: Query status
        print("\n" + "=" * 60)
        print("Test 2: Status Query")
        print("=" * 60)
        status = query_status(ser)
        if status is not None:
            if status == 0:
                print("Printer ready (status=0)")
            else:
                print(f"Printer status: {status}")
        else:
            print("No status response")

        input("\nPress Enter to test printing...")

        # Test 3: Print test image
        print("\n" + "=" * 60)
        print("Test 3: Print Test Image (BITMAP_SN)")
        print("=" * 60)

        # Create test image
        jpeg_data = create_test_image(120, 30)
        print(f"Created test image: 120x30, {len(jpeg_data)} bytes JPEG")

        # Try without compression first
        success = print_image(ser, jpeg_data, 120, 30, use_compression=False)

        if not success and HAS_LZO:
            print("\nTrying with LZO compression...")
            success = print_image(ser, jpeg_data, 120, 30, use_compression=True)

        if success:
            print("\nPrint successful!")
        else:
            print("\nPrint may have failed. Check printer.")

        # Test 4: Try old BITMAP protocol (without SN)
        input("\nPress Enter to try old BITMAP protocol...")

        print("\n" + "=" * 60)
        print("Test 4: Old BITMAP Protocol (no SN)")
        print("=" * 60)

        ser.reset_input_buffer()

        # SIZE command
        ser.write(b"SIZE 40 mm,10 mm\r\n")
        ser.flush()
        time.sleep(0.1)

        # CLS command
        ser.write(b"CLS\r\n")
        ser.flush()
        time.sleep(0.1)

        # BITMAP command (old format)
        header = f"BITMAP 0,0,120,30,0,4,{len(jpeg_data)},"
        packet = header.encode('ascii') + jpeg_data + CRLF
        print(f"Sending: {header}[{len(jpeg_data)} bytes JPEG]\\r\\n")
        send_chunked(ser, packet)
        time.sleep(0.2)

        # PRINT command
        ser.write(b"PRINT 1,1\r\n")
        ser.flush()

        response = wait_for_response(ser, timeout=5.0)
        if response:
            print(f"Response: {response.hex()}")
        else:
            print("No response (check if it printed)")

    finally:
        ser.close()
        print("\nSerial port closed.")


if __name__ == "__main__":
    main()
