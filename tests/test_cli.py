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


class TestScanAutoSelect:
    """Test scan command auto-select behavior."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_scan_auto_selects_single_printer(self, runner, mocker):
        """Test scan auto-selects when exactly one printer found."""
        from p31sprinter.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50)
        ]
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=mock_printers,
        )

        result = runner.invoke(main, ["scan", "--timeout", "1"])
        assert result.exit_code == 0
        assert "Found 1 printer: POLONO P31S - using automatically" in result.output
        assert "Address: AA:BB:CC:DD:EE:FF" in result.output

    def test_scan_no_auto_flag_shows_list_format(self, runner, mocker):
        """Test --no-auto flag shows list format even with one printer."""
        from p31sprinter.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50)
        ]
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=mock_printers,
        )

        result = runner.invoke(main, ["scan", "--timeout", "1", "--no-auto"])
        assert result.exit_code == 0
        assert "Found 1 printer(s):" in result.output
        assert "using automatically" not in result.output

    def test_scan_multiple_printers_shows_list(self, runner, mocker):
        """Test scan shows list format with multiple printers."""
        from p31sprinter.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50),
            PrinterInfo(name="P31S_2", address="11:22:33:44:55:66", rssi=-60),
        ]
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=mock_printers,
        )

        result = runner.invoke(main, ["scan", "--timeout", "1"])
        assert result.exit_code == 0
        assert "Found 2 printer(s):" in result.output
        assert "using automatically" not in result.output

    def test_scan_no_printers_found(self, runner, mocker):
        """Test scan shows message when no printers found."""
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=[],
        )

        result = runner.invoke(main, ["scan", "--timeout", "1"])
        assert result.exit_code == 0
        assert "No printers found." in result.output
