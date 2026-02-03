"""Tests for CLI functionality."""

import pytest
from click.testing import CliRunner

from p31sprinter.cli import (
    main,
    validate_bluetooth_address,
    BLUETOOTH_MAC_PATTERN,
)


class TestBluetoothAddressValidation:
    """Test CLI Bluetooth address validation."""

    def test_valid_address_returns_uppercase(self):
        """Test that valid address is returned uppercased."""
        result = validate_bluetooth_address(None, None, "aa:bb:cc:dd:ee:ff")
        assert result == "AA:BB:CC:DD:EE:FF"

    def test_valid_uppercase_address_unchanged(self):
        """Test that valid uppercase address is returned as-is."""
        result = validate_bluetooth_address(None, None, "AA:BB:CC:DD:EE:FF")
        assert result == "AA:BB:CC:DD:EE:FF"

    def test_invalid_address_raises_bad_parameter(self):
        """Test that invalid address raises click.BadParameter."""
        import click

        with pytest.raises(click.BadParameter) as exc_info:
            validate_bluetooth_address(None, None, "invalid")
        assert "Invalid Bluetooth address" in str(exc_info.value)
        assert "Expected format: XX:XX:XX:XX:XX:XX" in str(exc_info.value)


class TestCLIAddressValidation:
    """Test CLI commands reject invalid addresses."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_discover_rejects_invalid_address(self, runner):
        """Test discover command rejects invalid address."""
        result = runner.invoke(main, ["discover", "invalid-address"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_print_rejects_invalid_address(self, runner, tmp_path):
        """Test print command rejects invalid address."""
        # Create a dummy image file
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake png")

        result = runner.invoke(main, ["print", "bad", str(img_file)])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_test_rejects_invalid_address(self, runner):
        """Test test command rejects invalid address."""
        result = runner.invoke(main, ["test", "not-a-mac"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_raw_rejects_invalid_address(self, runner):
        """Test raw command rejects invalid address."""
        result = runner.invoke(main, ["raw", "wrong-format", "00"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_barcode_rejects_invalid_address(self, runner):
        """Test barcode command rejects invalid address."""
        result = runner.invoke(main, ["barcode", "xxx", "12345"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_qr_rejects_invalid_address(self, runner):
        """Test qr command rejects invalid address."""
        result = runner.invoke(main, ["qr", "bad-addr", "https://example.com"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_discover_accepts_valid_address(self, runner):
        """Test discover command accepts valid address format (will fail on connect, not validation)."""
        result = runner.invoke(main, ["discover", "AA:BB:CC:DD:EE:FF"])
        # Should not contain validation error - will fail later on actual connection
        assert "Invalid Bluetooth address" not in result.output
