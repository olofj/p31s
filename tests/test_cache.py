"""Tests for printer cache functionality."""

import json
import time

import pytest

from p31s.cache import (
    CachedPrinter,
    clear_cache,
    load_cached_printer,
    save_printer,
)


class TestCacheModule:
    """Test printer caching functionality."""

    @pytest.fixture(autouse=True)
    def setup_cache_dir(self, tmp_path, monkeypatch):
        """Set up temporary cache directory for each test."""
        test_config_dir = tmp_path / ".config" / "p31s"
        test_cache_file = test_config_dir / "last_printer"

        monkeypatch.setattr("p31s.cache.CONFIG_DIR", test_config_dir)
        monkeypatch.setattr("p31s.cache.CACHE_FILE", test_cache_file)

        self.config_dir = test_config_dir
        self.cache_file = test_cache_file

    def test_load_returns_none_when_no_cache(self):
        """Test load_cached_printer returns None when no cache exists."""
        result = load_cached_printer()
        assert result is None

    def test_save_creates_config_dir(self):
        """Test save_printer creates config directory if needed."""
        assert not self.config_dir.exists()
        save_printer("AA:BB:CC:DD:EE:FF", "Test Printer")
        assert self.config_dir.exists()
        assert self.cache_file.exists()

    def test_save_and_load_roundtrip(self):
        """Test saving and loading printer data."""
        address = "AA:BB:CC:DD:EE:FF"
        name = "Test Printer"

        save_printer(address, name)
        cached = load_cached_printer()

        assert cached is not None
        assert cached.address == address
        assert cached.name == name
        assert cached.last_used <= time.time()

    def test_load_returns_none_for_expired_cache(self):
        """Test load_cached_printer returns None when cache is expired."""
        # Save with old timestamp
        self.config_dir.mkdir(parents=True, exist_ok=True)
        old_time = time.time() - 25 * 60 * 60  # 25 hours ago
        data = {
            "address": "AA:BB:CC:DD:EE:FF",
            "name": "Test Printer",
            "last_used": old_time,
        }
        self.cache_file.write_text(json.dumps(data))

        result = load_cached_printer()
        assert result is None

    def test_load_respects_custom_ttl(self):
        """Test load_cached_printer respects custom TTL."""
        # Save with timestamp 2 hours ago
        self.config_dir.mkdir(parents=True, exist_ok=True)
        two_hours_ago = time.time() - 2 * 60 * 60
        data = {
            "address": "AA:BB:CC:DD:EE:FF",
            "name": "Test Printer",
            "last_used": two_hours_ago,
        }
        self.cache_file.write_text(json.dumps(data))

        # Should still be valid with default 24h TTL
        result = load_cached_printer()
        assert result is not None

        # Should be expired with 1 hour TTL
        result = load_cached_printer(ttl_seconds=3600)
        assert result is None

    def test_load_returns_none_for_invalid_json(self):
        """Test load_cached_printer returns None for invalid JSON."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text("not valid json")

        result = load_cached_printer()
        assert result is None

    def test_load_returns_none_for_missing_fields(self):
        """Test load_cached_printer returns None for missing fields."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {"address": "AA:BB:CC:DD:EE:FF"}  # Missing name and last_used
        self.cache_file.write_text(json.dumps(data))

        result = load_cached_printer()
        assert result is None

    def test_clear_cache_removes_file(self):
        """Test clear_cache removes the cache file."""
        save_printer("AA:BB:CC:DD:EE:FF", "Test Printer")
        assert self.cache_file.exists()

        result = clear_cache()
        assert result is True
        assert not self.cache_file.exists()

    def test_clear_cache_returns_false_when_no_cache(self):
        """Test clear_cache returns False when no cache exists."""
        result = clear_cache()
        assert result is False

    def test_save_overwrites_existing_cache(self):
        """Test save_printer overwrites existing cache."""
        save_printer("AA:BB:CC:DD:EE:FF", "First Printer")
        save_printer("11:22:33:44:55:66", "Second Printer")

        cached = load_cached_printer()
        assert cached is not None
        assert cached.address == "11:22:33:44:55:66"
        assert cached.name == "Second Printer"

    def test_cached_printer_dataclass(self):
        """Test CachedPrinter dataclass initialization."""
        cached = CachedPrinter(
            address="AA:BB:CC:DD:EE:FF",
            name="Test Printer",
            last_used=1234567890.0,
        )
        assert cached.address == "AA:BB:CC:DD:EE:FF"
        assert cached.name == "Test Printer"
        assert cached.last_used == 1234567890.0
