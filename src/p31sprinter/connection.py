"""
BLE Connection Handler for P31S Printer.

Handles Bluetooth Low Energy communication using the Bleak library.
"""

import asyncio
from dataclasses import dataclass
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice


@dataclass
class PrinterInfo:
    """Information about a discovered printer."""
    name: str
    address: str
    rssi: int

    def __str__(self) -> str:
        return f"{self.name} [{self.address}] RSSI: {self.rssi} dB"


@dataclass
class ServiceInfo:
    """Information about a GATT service and its characteristics."""
    service_uuid: str
    characteristics: list[dict]


class BLEConnection:
    """Manages BLE connection to P31S printer."""

    # Known device name patterns
    DEVICE_PATTERNS = ["P31", "POLONO", "MAKEID", "NIIMBOT", "LABEL"]

    # Response queue limits (security: prevent memory exhaustion from malicious devices)
    MAX_QUEUE_SIZE = 100  # Maximum number of queued notifications
    MAX_RESPONSE_SIZE = 4096  # Maximum size of a single notification (bytes)

    # Primary service/characteristic UUIDs (discovered from Labelnize APK)
    PRIMARY_SERVICE = "0000ff00-0000-1000-8000-00805f9b34fb"
    CHAR_READ = "0000ff01-0000-1000-8000-00805f9b34fb"
    CHAR_WRITE = "0000ff02-0000-1000-8000-00805f9b34fb"
    CHAR_NOTIFY = "0000ff03-0000-1000-8000-00805f9b34fb"

    # Alternative UUIDs for other printer models
    ALT_SERVICE = "0000ae00-0000-1000-8000-00805f9b34fb"
    ALT_CHAR_WRITE = "0000ae01-0000-1000-8000-00805f9b34fb"
    ALT_CHAR_NOTIFY = "0000ae02-0000-1000-8000-00805f9b34fb"

    # Common BLE UART service UUIDs to try
    KNOWN_SERVICE_UUIDS = [
        PRIMARY_SERVICE,  # Labelnize primary service
        ALT_SERVICE,  # Alternative vendor service
        "6e400001-b5a3-f393-e0a9-e50e24dcca9e",  # Nordic UART Service
        "49535343-fe7d-4ae5-8fa9-9fafd205e455",  # Microchip UART
    ]

    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.device: Optional[BLEDevice] = None
        self.write_char: Optional[str] = None
        self.notify_char: Optional[str] = None
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._notification_callback: Optional[Callable] = None

    @classmethod
    async def scan(cls, timeout: float = 10.0) -> list[PrinterInfo]:
        """Scan for P31S printers."""
        printers = []
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

        for device, adv_data in devices.values():
            name = device.name or ""
            if any(pattern.upper() in name.upper() for pattern in cls.DEVICE_PATTERNS):
                printers.append(PrinterInfo(
                    name=name,
                    address=device.address,
                    rssi=adv_data.rssi if adv_data.rssi is not None else -100
                ))

        return sorted(printers, key=lambda p: p.rssi, reverse=True)

    async def connect(self, address: str) -> bool:
        """Connect to a printer by address."""
        self.client = BleakClient(address)

        try:
            await self.client.connect()

            # Discover services and find write/notify characteristics
            await self._discover_characteristics()

            # Set up notification handler if we found a notify characteristic
            if self.notify_char:
                await self.client.start_notify(
                    self.notify_char,
                    self._handle_notification
                )

            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the printer."""
        if self.client and self.client.is_connected:
            if self.notify_char:
                try:
                    await self.client.stop_notify(self.notify_char)
                except Exception:
                    pass
            await self.client.disconnect()
        self.client = None
        self.write_char = None
        self.notify_char = None

    async def _discover_characteristics(self):
        """Find write and notify characteristics."""
        if not self.client:
            return

        for service in self.client.services:
            for char in service.characteristics:
                props = char.properties

                # Find writable characteristic
                if "write" in props or "write-without-response" in props:
                    if not self.write_char:
                        self.write_char = char.uuid
                        print(f"Found write characteristic: {char.uuid}")

                # Find notify characteristic
                if "notify" in props or "indicate" in props:
                    if not self.notify_char:
                        self.notify_char = char.uuid
                        print(f"Found notify characteristic: {char.uuid}")

    def _handle_notification(self, sender: BleakGATTCharacteristic, data: bytearray):
        """Handle incoming notifications from the printer."""
        # Security: reject oversized responses
        if len(data) > self.MAX_RESPONSE_SIZE:
            return

        # Security: if queue is full, drop oldest item to prevent memory exhaustion
        if self._response_queue.qsize() >= self.MAX_QUEUE_SIZE:
            try:
                self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        self._response_queue.put_nowait(bytes(data))

        if self._notification_callback:
            self._notification_callback(bytes(data))

    def set_notification_callback(self, callback: Callable[[bytes], None]):
        """Set a callback for incoming notifications."""
        self._notification_callback = callback

    # Default chunk size for BLE writes
    # iOS capture shows MTU of 124, so ~121 byte chunks work
    # Using 100 as a safe default that works with most BLE connections
    DEFAULT_CHUNK_SIZE = 100

    async def write(self, data: bytes, response: bool = False) -> bool:
        """Write data to the printer."""
        if not self.client or not self.write_char:
            return False

        try:
            await self.client.write_gatt_char(
                self.write_char,
                data,
                response=response
            )
            return True
        except Exception as e:
            print(f"Write failed: {e}")
            return False

    async def write_chunked(
        self,
        data: bytes,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        delay_ms: float = 10.0,
        response: bool = False
    ) -> bool:
        """
        Write data to the printer in chunks.

        Args:
            data: Data to write
            chunk_size: Maximum bytes per chunk (default 20, safe for most BLE)
            delay_ms: Delay between chunks in milliseconds
            response: Whether to wait for write response

        Returns:
            True if all chunks were written successfully
        """
        if not self.client or not self.write_char:
            return False

        total_chunks = (len(data) + chunk_size - 1) // chunk_size

        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            chunk_num = i // chunk_size + 1

            try:
                await self.client.write_gatt_char(
                    self.write_char,
                    chunk,
                    response=response
                )
            except Exception as e:
                print(f"Write failed at chunk {chunk_num}/{total_chunks}: {e}")
                return False

            # Small delay between chunks to avoid overwhelming the printer
            if delay_ms > 0 and i + chunk_size < len(data):
                await asyncio.sleep(delay_ms / 1000.0)

        return True

    async def get_mtu(self) -> int:
        """Get the negotiated MTU size."""
        if not self.client:
            return self.DEFAULT_CHUNK_SIZE

        try:
            # Bleak provides mtu_size on some backends
            mtu = getattr(self.client, 'mtu_size', None)
            if mtu:
                # MTU includes 3 bytes of ATT overhead
                return max(mtu - 3, self.DEFAULT_CHUNK_SIZE)
        except Exception:
            pass

        return self.DEFAULT_CHUNK_SIZE

    async def read_response(self, timeout: float = 5.0) -> Optional[bytes]:
        """Wait for and return a response from the printer."""
        try:
            return await asyncio.wait_for(
                self._response_queue.get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

    async def get_services(self) -> list[ServiceInfo]:
        """Get all services and characteristics (for discovery)."""
        if not self.client:
            return []

        services = []
        for service in self.client.services:
            chars = []
            for char in service.characteristics:
                chars.append({
                    "uuid": char.uuid,
                    "properties": list(char.properties),
                    "handle": char.handle,
                })
            services.append(ServiceInfo(
                service_uuid=service.uuid,
                characteristics=chars
            ))

        return services

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.client is not None and self.client.is_connected
