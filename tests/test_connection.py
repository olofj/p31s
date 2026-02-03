"""Tests for BLE connection handling."""

from unittest.mock import MagicMock, patch

from p31s.connection import BLEConnection, PrinterInfo


class TestNotificationSizeLimits:
    """Test notification handler size limits."""

    def test_max_queue_size_constant(self):
        """Verify MAX_QUEUE_SIZE constant is defined."""
        assert BLEConnection.MAX_QUEUE_SIZE == 100

    def test_max_response_size_constant(self):
        """Verify MAX_RESPONSE_SIZE constant is defined."""
        assert BLEConnection.MAX_RESPONSE_SIZE == 4096

    def test_rejects_oversized_response(self):
        """Notification handler should reject oversized responses."""
        conn = BLEConnection()
        mock_sender = MagicMock()

        # Create data larger than MAX_RESPONSE_SIZE
        oversized_data = bytearray(BLEConnection.MAX_RESPONSE_SIZE + 1)
        conn._handle_notification(mock_sender, oversized_data)

        # Queue should be empty - oversized data was rejected
        assert conn._response_queue.qsize() == 0

    def test_accepts_max_size_response(self):
        """Notification handler should accept data at exactly MAX_RESPONSE_SIZE."""
        conn = BLEConnection()
        mock_sender = MagicMock()

        # Create data exactly at MAX_RESPONSE_SIZE
        max_data = bytearray(BLEConnection.MAX_RESPONSE_SIZE)
        conn._handle_notification(mock_sender, max_data)

        # Data should be queued
        assert conn._response_queue.qsize() == 1

    def test_accepts_small_response(self):
        """Notification handler should accept small responses."""
        conn = BLEConnection()
        mock_sender = MagicMock()

        small_data = bytearray(b"OK")
        conn._handle_notification(mock_sender, small_data)

        assert conn._response_queue.qsize() == 1

    def test_queue_drops_oldest_when_full(self):
        """Verify oldest notification is dropped when queue is full."""
        conn = BLEConnection()
        mock_sender = MagicMock()

        # Fill queue exactly to MAX_QUEUE_SIZE
        for i in range(BLEConnection.MAX_QUEUE_SIZE):
            data = bytearray([i % 256])
            conn._handle_notification(mock_sender, data)

        # Queue should be full
        assert conn._response_queue.qsize() == BLEConnection.MAX_QUEUE_SIZE

        # Add one more item
        conn._handle_notification(mock_sender, bytearray([0xAA]))

        # Queue size should remain at MAX_QUEUE_SIZE
        assert conn._response_queue.qsize() == BLEConnection.MAX_QUEUE_SIZE

        # First item (oldest) should have been dropped
        # The new first item should be index 1 (index 0 was dropped)
        first = conn._response_queue.get_nowait()
        assert first == bytes([1])

    def test_notification_callback_still_called(self):
        """Notification callback should still be called for valid data."""
        conn = BLEConnection()
        mock_sender = MagicMock()
        callback_data = []

        def callback(data: bytes):
            callback_data.append(data)

        conn.set_notification_callback(callback)
        conn._handle_notification(mock_sender, bytearray(b"test"))

        assert len(callback_data) == 1
        assert callback_data[0] == b"test"

    def test_notification_callback_not_called_for_oversized(self):
        """Notification callback should not be called for oversized data."""
        conn = BLEConnection()
        mock_sender = MagicMock()
        callback_data = []

        def callback(data: bytes):
            callback_data.append(data)

        conn.set_notification_callback(callback)

        # Send oversized data
        oversized = bytearray(BLEConnection.MAX_RESPONSE_SIZE + 1)
        conn._handle_notification(mock_sender, oversized)

        # Callback should not have been called
        assert len(callback_data) == 0


class TestPrinterInfo:
    """Tests for PrinterInfo dataclass."""

    def test_str_with_mac_equals_address(self):
        """PrinterInfo string shows simple format when MAC equals address."""
        info = PrinterInfo(
            name="P31S-1234",
            address="AA:BB:CC:DD:EE:FF",
            rssi=-45,
            mac_address="AA:BB:CC:DD:EE:FF",
        )
        result = str(info)
        assert result == "P31S-1234 [AA:BB:CC:DD:EE:FF] RSSI: -45 dB"

    def test_str_with_different_mac_and_address(self):
        """PrinterInfo string shows MAC prominently with UUID secondary on macOS."""
        info = PrinterInfo(
            name="P31S-1234",
            address="8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D",
            rssi=-45,
            mac_address="AA:BB:CC:DD:EE:FF",
        )
        result = str(info)
        assert "AA:BB:CC:DD:EE:FF" in result
        assert "macOS UUID:" in result
        assert "8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D" in result

    def test_str_without_mac(self):
        """PrinterInfo string shows address when MAC is None."""
        info = PrinterInfo(
            name="P31S-1234",
            address="8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D",
            rssi=-45,
            mac_address=None,
        )
        result = str(info)
        assert "8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D" in result
        assert "macOS UUID:" not in result


class TestMacExtraction:
    """Tests for MAC address extraction from manufacturer data."""

    def test_extract_mac_from_first_6_bytes(self):
        """Extract MAC from first 6 bytes of manufacturer data."""
        # Manufacturer data with MAC in first 6 bytes
        manufacturer_data = {0x1234: bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF])}
        mac = BLEConnection._extract_mac_from_manufacturer_data(manufacturer_data)
        assert mac == "AA:BB:CC:DD:EE:FF"

    def test_extract_mac_from_longer_data(self):
        """Extract MAC from manufacturer data with extra bytes."""
        # MAC followed by additional data
        manufacturer_data = {0x1234: bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x00, 0x01, 0x02])}
        mac = BLEConnection._extract_mac_from_manufacturer_data(manufacturer_data)
        assert mac == "11:22:33:44:55:66"

    def test_rejects_all_zeros_mac(self):
        """Reject MAC address that is all zeros."""
        manufacturer_data = {0x1234: bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])}
        mac = BLEConnection._extract_mac_from_manufacturer_data(manufacturer_data)
        assert mac is None

    def test_rejects_all_ones_mac(self):
        """Reject MAC address that is all 0xFF."""
        manufacturer_data = {0x1234: bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])}
        mac = BLEConnection._extract_mac_from_manufacturer_data(manufacturer_data)
        assert mac is None

    def test_empty_manufacturer_data(self):
        """Return None for empty manufacturer data."""
        mac = BLEConnection._extract_mac_from_manufacturer_data({})
        assert mac is None

    def test_too_short_data(self):
        """Return None when data is too short for MAC."""
        manufacturer_data = {0x1234: bytes([0xAA, 0xBB, 0xCC])}
        mac = BLEConnection._extract_mac_from_manufacturer_data(manufacturer_data)
        assert mac is None

    def test_multiple_company_ids(self):
        """Handle multiple company IDs in manufacturer data."""
        manufacturer_data = {
            0x0000: bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),  # Invalid
            0x1234: bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]),  # Valid
        }
        mac = BLEConnection._extract_mac_from_manufacturer_data(manufacturer_data)
        # Should find the valid MAC from second entry
        assert mac is not None


class TestPlatformDetection:
    """Tests for macOS platform detection."""

    def test_is_macos_on_darwin(self):
        """_is_macos returns True on Darwin."""
        with patch("p31s.connection.platform.system", return_value="Darwin"):
            assert BLEConnection._is_macos() is True

    def test_is_macos_on_linux(self):
        """_is_macos returns False on Linux."""
        with patch("p31s.connection.platform.system", return_value="Linux"):
            assert BLEConnection._is_macos() is False

    def test_is_macos_on_windows(self):
        """_is_macos returns False on Windows."""
        with patch("p31s.connection.platform.system", return_value="Windows"):
            assert BLEConnection._is_macos() is False
