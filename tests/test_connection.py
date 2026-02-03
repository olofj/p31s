"""Tests for BLE connection handling."""

import asyncio
from unittest.mock import MagicMock

import pytest

from p31sprinter.connection import BLEConnection


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
