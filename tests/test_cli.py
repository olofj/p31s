"""Tests for CLI functionality."""

import pytest
from click.testing import CliRunner

from p31sprinter.cli import (
    main,
    validate_bluetooth_address,
    scan_and_select,
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

    def test_none_address_returns_none(self):
        """Test that None address returns None (allows optional address)."""
        result = validate_bluetooth_address(None, None, None)
        assert result is None


class TestCLIAddressValidation:
    """Test CLI commands reject invalid addresses when provided via --address."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_discover_rejects_invalid_address(self, runner):
        """Test discover command rejects invalid address."""
        result = runner.invoke(main, ["discover", "--address", "invalid-address"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_print_rejects_invalid_address(self, runner, tmp_path):
        """Test print command rejects invalid address."""
        # Create a dummy image file
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake png")

        result = runner.invoke(main, ["print", str(img_file), "--address", "bad"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_test_rejects_invalid_address(self, runner):
        """Test test command rejects invalid address."""
        result = runner.invoke(main, ["test", "--address", "not-a-mac"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_raw_rejects_invalid_address(self, runner):
        """Test raw command rejects invalid address."""
        result = runner.invoke(main, ["raw", "00", "--address", "wrong-format"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_barcode_rejects_invalid_address(self, runner):
        """Test barcode command rejects invalid address."""
        result = runner.invoke(main, ["barcode", "12345", "--address", "xxx"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_qr_rejects_invalid_address(self, runner):
        """Test qr command rejects invalid address."""
        result = runner.invoke(main, ["qr", "https://example.com", "--address", "bad-addr"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output

    def test_discover_accepts_valid_address(self, runner):
        """Test discover command accepts valid address format (will fail on connect, not validation)."""
        result = runner.invoke(main, ["discover", "--address", "AA:BB:CC:DD:EE:FF"])
        # Should not contain validation error - will fail later on actual connection
        assert "Invalid Bluetooth address" not in result.output

    def test_test_coverage_rejects_invalid_address(self, runner):
        """Test test-coverage command rejects invalid address."""
        result = runner.invoke(main, ["test-coverage", "--address", "not-valid"])
        assert result.exit_code != 0
        assert "Invalid Bluetooth address" in result.output


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


class TestInteractiveSelection:
    """Test interactive printer selection when no address is provided."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_print_without_address_scans_and_selects(self, runner, mocker, tmp_path):
        """Test print command scans and auto-selects single printer."""
        from p31sprinter.connection import PrinterInfo

        img_file = tmp_path / "test.png"
        # Create a minimal valid PNG
        from PIL import Image

        img = Image.new("RGB", (10, 10), color="white")
        img.save(img_file)

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50)
        ]
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=mock_printers,
        )

        # Mock connect to return True
        async def mock_connect(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.connect",
            side_effect=mock_connect,
        )

        # Mock print_image to return True
        async def mock_print(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.print_image",
            side_effect=mock_print,
        )

        # Mock disconnect
        async def mock_disconnect(*args, **kwargs):
            pass

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.disconnect",
            side_effect=mock_disconnect,
        )

        result = runner.invoke(main, ["print", str(img_file)])
        assert result.exit_code == 0
        assert "Found 1 printer: POLONO P31S - using automatically" in result.output
        assert "Print complete!" in result.output

    def test_test_without_address_scans_single_printer(self, runner, mocker):
        """Test test command scans and auto-selects single printer."""
        from p31sprinter.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50)
        ]
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=mock_printers,
        )

        async def mock_connect(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.connect",
            side_effect=mock_connect,
        )

        async def mock_print_test(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.print_test_pattern",
            side_effect=mock_print_test,
        )

        async def mock_disconnect(*args, **kwargs):
            pass

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.disconnect",
            side_effect=mock_disconnect,
        )

        result = runner.invoke(main, ["test"])
        assert result.exit_code == 0
        assert "Found 1 printer: POLONO P31S - using automatically" in result.output
        assert "Test print complete!" in result.output

    def test_command_without_address_exits_when_no_printers(self, runner, mocker):
        """Test commands exit with error when no printers found."""
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=[],
        )

        result = runner.invoke(main, ["test"])
        assert result.exit_code == 1
        assert "No printers found." in result.output

    def test_interactive_selection_with_multiple_printers(self, runner, mocker):
        """Test interactive prompt appears with multiple printers."""
        from p31sprinter.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50),
            PrinterInfo(name="P31S_2", address="11:22:33:44:55:66", rssi=-60),
        ]
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=mock_printers,
        )

        async def mock_connect(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.connect",
            side_effect=mock_connect,
        )

        async def mock_print_test(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.print_test_pattern",
            side_effect=mock_print_test,
        )

        async def mock_disconnect(*args, **kwargs):
            pass

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.disconnect",
            side_effect=mock_disconnect,
        )

        # Simulate user selecting option 1
        result = runner.invoke(main, ["test"], input="1\n")
        assert result.exit_code == 0
        assert "Found 2 printer(s):" in result.output
        assert "[1]" in result.output
        assert "[2]" in result.output
        assert "Select printer (1-2):" in result.output
        assert "Selected: POLONO P31S" in result.output

    def test_interactive_selection_second_option(self, runner, mocker):
        """Test selecting second printer in interactive mode."""
        from p31sprinter.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50),
            PrinterInfo(name="P31S_2", address="11:22:33:44:55:66", rssi=-60),
        ]
        mocker.patch(
            "p31sprinter.cli.P31SPrinter.scan",
            return_value=mock_printers,
        )

        async def mock_connect(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.connect",
            side_effect=mock_connect,
        )

        async def mock_print_test(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.print_test_pattern",
            side_effect=mock_print_test,
        )

        async def mock_disconnect(*args, **kwargs):
            pass

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.disconnect",
            side_effect=mock_disconnect,
        )

        # Simulate user selecting option 2
        result = runner.invoke(main, ["test"], input="2\n")
        assert result.exit_code == 0
        assert "Selected: P31S_2" in result.output

    def test_address_option_short_form(self, runner, mocker):
        """Test using -a short form for address option."""
        async def mock_connect(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.connect",
            side_effect=mock_connect,
        )

        async def mock_print_test(*args, **kwargs):
            return True

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.print_test_pattern",
            side_effect=mock_print_test,
        )

        async def mock_disconnect(*args, **kwargs):
            pass

        mocker.patch(
            "p31sprinter.cli.P31SPrinter.disconnect",
            side_effect=mock_disconnect,
        )

        result = runner.invoke(main, ["test", "-a", "AA:BB:CC:DD:EE:FF"])
        assert result.exit_code == 0
        # Should not scan, should go straight to connect
        assert "Scanning" not in result.output
        assert "Connecting to AA:BB:CC:DD:EE:FF" in result.output
