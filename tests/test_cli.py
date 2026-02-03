"""Tests for CLI functionality."""

import pytest
from click.testing import CliRunner

from p31s.cli import (
    _format_printer_address,
    _get_connect_address,
    main,
    validate_bluetooth_address,
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
        assert "XX:XX:XX:XX:XX:XX" in str(exc_info.value)

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

    def test_scan_auto_selects_single_printer(self, runner, monkeypatch):
        """Test scan auto-selects when exactly one printer found."""
        import p31s.cli
        from p31s.connection import PrinterInfo

        mock_printers = [PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50)]

        async def mock_scan(timeout=10.0):
            return mock_printers

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["scan", "--timeout", "1"])
        assert result.exit_code == 0
        assert "Found 1 printer: POLONO P31S - using automatically" in result.output
        assert "Address: AA:BB:CC:DD:EE:FF" in result.output

    def test_scan_no_auto_flag_shows_list_format(self, runner, monkeypatch):
        """Test --no-auto flag shows list format even with one printer."""
        import p31s.cli
        from p31s.connection import PrinterInfo

        mock_printers = [PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50)]

        async def mock_scan(timeout=10.0):
            return mock_printers

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["scan", "--timeout", "1", "--no-auto"])
        assert result.exit_code == 0
        assert "Found 1 printer(s):" in result.output
        assert "using automatically" not in result.output

    def test_scan_multiple_printers_shows_list(self, runner, monkeypatch):
        """Test scan shows list format with multiple printers."""
        import p31s.cli
        from p31s.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50),
            PrinterInfo(name="P31S_2", address="11:22:33:44:55:66", rssi=-60),
        ]

        async def mock_scan(timeout=10.0):
            return mock_printers

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["scan", "--timeout", "1"])
        assert result.exit_code == 0
        assert "Found 2 printer(s):" in result.output
        assert "using automatically" not in result.output

    def test_scan_no_printers_found(self, runner, monkeypatch):
        """Test scan shows message when no printers found."""
        import p31s.cli

        async def mock_scan(timeout=10.0):
            return []

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["scan", "--timeout", "1"])
        assert result.exit_code == 0
        assert "No printers found." in result.output


class TestInteractiveSelection:
    """Test interactive printer selection when no address is provided."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_print_without_address_scans_and_selects(self, runner, monkeypatch, tmp_path):
        """Test print command scans and auto-selects single printer."""
        from PIL import Image

        import p31s.cli
        from p31s.connection import PrinterInfo

        img_file = tmp_path / "test.png"
        img = Image.new("RGB", (10, 10), color="white")
        img.save(img_file)

        mock_printers = [PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50)]

        async def mock_scan(timeout=10.0):
            return mock_printers

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_image", mock_print)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        result = runner.invoke(main, ["print", str(img_file)])
        assert result.exit_code == 0
        assert "Found 1 printer: POLONO P31S - using automatically" in result.output
        assert "Print complete!" in result.output

    def test_test_without_address_scans_single_printer(self, runner, monkeypatch):
        """Test test command scans and auto-selects single printer."""
        import p31s.cli
        from p31s.connection import PrinterInfo

        mock_printers = [PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50)]

        async def mock_scan(timeout=10.0):
            return mock_printers

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print_test(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_test_pattern", mock_print_test)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        result = runner.invoke(main, ["test"])
        assert result.exit_code == 0
        assert "Found 1 printer: POLONO P31S - using automatically" in result.output
        assert "Test print complete!" in result.output

    def test_command_without_address_exits_when_no_printers(self, runner, monkeypatch):
        """Test commands exit with error when no printers found."""
        import p31s.cli

        async def mock_scan(timeout=10.0):
            return []

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["test"])
        assert result.exit_code == 1
        assert "No printers found." in result.output

    def test_interactive_selection_with_multiple_printers(self, runner, monkeypatch):
        """Test interactive prompt appears with multiple printers."""
        import p31s.cli
        from p31s.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50),
            PrinterInfo(name="P31S_2", address="11:22:33:44:55:66", rssi=-60),
        ]

        async def mock_scan(timeout=10.0):
            return mock_printers

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print_test(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_test_pattern", mock_print_test)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        # Simulate user selecting option 1
        result = runner.invoke(main, ["test"], input="1\n")
        assert result.exit_code == 0
        assert "Found 2 printer(s):" in result.output
        assert "[1]" in result.output
        assert "[2]" in result.output
        assert "Select printer (1-2):" in result.output
        assert "Selected: POLONO P31S" in result.output

    def test_interactive_selection_second_option(self, runner, monkeypatch):
        """Test selecting second printer in interactive mode."""
        import p31s.cli
        from p31s.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(name="POLONO P31S", address="AA:BB:CC:DD:EE:FF", rssi=-50),
            PrinterInfo(name="P31S_2", address="11:22:33:44:55:66", rssi=-60),
        ]

        async def mock_scan(timeout=10.0):
            return mock_printers

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print_test(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_test_pattern", mock_print_test)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        # Simulate user selecting option 2
        result = runner.invoke(main, ["test"], input="2\n")
        assert result.exit_code == 0
        assert "Selected: P31S_2" in result.output

    def test_address_option_short_form(self, runner, monkeypatch):
        """Test using -a short form for address option."""
        import p31s.cli

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print_test(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_test_pattern", mock_print_test)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        result = runner.invoke(main, ["test", "-a", "AA:BB:CC:DD:EE:FF"])
        assert result.exit_code == 0
        # Should not scan, should go straight to connect
        assert "Scanning" not in result.output
        assert "Connecting to AA:BB:CC:DD:EE:FF" in result.output


class TestMacAddressHelpers:
    """Test MAC address helper functions."""

    def test_get_connect_address_prefers_mac(self):
        """_get_connect_address returns MAC address when available."""
        from p31s.connection import PrinterInfo

        info = PrinterInfo(
            name="P31S-1234",
            address="8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D",
            rssi=-45,
            mac_address="AA:BB:CC:DD:EE:FF",
        )
        assert _get_connect_address(info) == "AA:BB:CC:DD:EE:FF"

    def test_get_connect_address_fallback_to_address(self):
        """_get_connect_address falls back to address when MAC is None."""
        from p31s.connection import PrinterInfo

        info = PrinterInfo(
            name="P31S-1234",
            address="8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D",
            rssi=-45,
            mac_address=None,
        )
        assert _get_connect_address(info) == "8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D"

    def test_format_printer_address_shows_mac_with_uuid(self):
        """_format_printer_address shows MAC with UUID on macOS."""
        from p31s.connection import PrinterInfo

        info = PrinterInfo(
            name="P31S-1234",
            address="8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D",
            rssi=-45,
            mac_address="AA:BB:CC:DD:EE:FF",
        )
        result = _format_printer_address(info)
        assert "AA:BB:CC:DD:EE:FF" in result
        assert "macOS UUID:" in result
        assert "8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D" in result

    def test_format_printer_address_simple_when_same(self):
        """_format_printer_address shows simple format when MAC equals address."""
        from p31s.connection import PrinterInfo

        info = PrinterInfo(
            name="P31S-1234",
            address="AA:BB:CC:DD:EE:FF",
            rssi=-45,
            mac_address="AA:BB:CC:DD:EE:FF",
        )
        result = _format_printer_address(info)
        assert result == "AA:BB:CC:DD:EE:FF"
        assert "macOS UUID:" not in result

    def test_format_printer_address_fallback_when_no_mac(self):
        """_format_printer_address shows address when MAC is None."""
        from p31s.connection import PrinterInfo

        info = PrinterInfo(
            name="P31S-1234",
            address="8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D",
            rssi=-45,
            mac_address=None,
        )
        result = _format_printer_address(info)
        assert result == "8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D"


class TestScanTimeoutValidation:
    """Test scan command timeout parameter validation."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_timeout_too_low_rejected(self, runner):
        """Test timeout below 1.0 is rejected."""
        result = runner.invoke(main, ["scan", "--timeout", "0.5"])
        assert result.exit_code != 0
        assert (
            "0.5 is not in the range" in result.output
            or "1.0<=x<=300.0" in result.output.replace(" ", "")
        )

    def test_timeout_too_high_rejected(self, runner):
        """Test timeout above 300.0 is rejected."""
        result = runner.invoke(main, ["scan", "--timeout", "500"])
        assert result.exit_code != 0
        assert "500" in result.output or "300.0" in result.output

    def test_timeout_at_lower_bound_accepted(self, runner, monkeypatch):
        """Test timeout of exactly 1.0 is accepted."""
        import p31s.cli

        async def mock_scan(timeout=10.0):
            return []

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["scan", "--timeout", "1.0"])
        assert result.exit_code == 0
        assert "Scanning for printers (1.0s)" in result.output

    def test_timeout_at_upper_bound_accepted(self, runner, monkeypatch):
        """Test timeout of exactly 300.0 is accepted."""
        import p31s.cli

        async def mock_scan(timeout=10.0):
            return []

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["scan", "--timeout", "300.0"])
        assert result.exit_code == 0
        assert "Scanning for printers (300.0s)" in result.output

    def test_timeout_default_accepted(self, runner, monkeypatch):
        """Test default timeout of 10.0 is accepted."""
        import p31s.cli

        async def mock_scan(timeout=10.0):
            return []

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["scan"])
        assert result.exit_code == 0
        assert "Scanning for printers (10.0s)" in result.output


class TestScanWithMacAddresses:
    """Test scan command output with MAC addresses on macOS."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_scan_shows_mac_on_macos(self, runner, monkeypatch):
        """Test scan shows extracted MAC address on macOS."""
        import p31s.cli
        from p31s.connection import PrinterInfo

        # Simulate macOS with extracted MAC
        mock_printers = [
            PrinterInfo(
                name="POLONO P31S",
                address="8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D",
                rssi=-50,
                mac_address="AA:BB:CC:DD:EE:FF",
            )
        ]

        async def mock_scan(timeout=10.0):
            return mock_printers

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)

        result = runner.invoke(main, ["scan", "--timeout", "1"])
        assert result.exit_code == 0
        assert "AA:BB:CC:DD:EE:FF" in result.output
        assert "macOS UUID:" in result.output

    def test_scan_uses_mac_for_auto_select(self, runner, monkeypatch):
        """Test auto-select uses MAC address when available."""
        import p31s.cli
        from p31s.connection import PrinterInfo

        mock_printers = [
            PrinterInfo(
                name="POLONO P31S",
                address="8C56F3E2-7A1D-4B3C-9E8A-1F2D3C4B5A6D",
                rssi=-50,
                mac_address="AA:BB:CC:DD:EE:FF",
            )
        ]

        async def mock_scan(timeout=10.0):
            return mock_printers

        async def mock_connect(self, address, *args, **kwargs):
            # Verify we're connecting with the MAC address, not UUID
            assert address == "AA:BB:CC:DD:EE:FF"
            return True

        async def mock_print_test(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "scan", mock_scan)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_test_pattern", mock_print_test)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        result = runner.invoke(main, ["test"])
        assert result.exit_code == 0
        assert "Connecting to AA:BB:CC:DD:EE:FF" in result.output


class TestCopiesAndRetryBoundsValidation:
    """Test bounds checking for --copies and --retry parameters."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_image_file(self, tmp_path):
        """Create a test image file."""
        from PIL import Image

        img_file = tmp_path / "test.png"
        img = Image.new("RGB", (10, 10), color="white")
        img.save(img_file)
        return str(img_file)

    # --copies validation tests

    def test_print_copies_below_minimum_rejected(self, runner, mock_image_file):
        """Test --copies=0 is rejected (minimum is 1)."""
        result = runner.invoke(
            main, ["print", mock_image_file, "--address", "AA:BB:CC:DD:EE:FF", "--copies", "0"]
        )
        assert result.exit_code != 0
        assert "0 is not in the range" in result.output or "1<=x<=100" in result.output.replace(
            " ", ""
        )

    def test_print_copies_above_maximum_rejected(self, runner, mock_image_file):
        """Test --copies=101 is rejected (maximum is 100)."""
        result = runner.invoke(
            main, ["print", mock_image_file, "--address", "AA:BB:CC:DD:EE:FF", "--copies", "101"]
        )
        assert result.exit_code != 0
        assert "101" in result.output or "100" in result.output

    def test_print_copies_at_minimum_accepted(self, runner, mock_image_file, monkeypatch):
        """Test --copies=1 is accepted."""
        import p31s.cli

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_image", mock_print)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        result = runner.invoke(
            main, ["print", mock_image_file, "--address", "AA:BB:CC:DD:EE:FF", "--copies", "1"]
        )
        assert result.exit_code == 0

    def test_print_copies_at_maximum_accepted(self, runner, mock_image_file, monkeypatch):
        """Test --copies=100 is accepted."""
        import p31s.cli

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_image", mock_print)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        result = runner.invoke(
            main, ["print", mock_image_file, "--address", "AA:BB:CC:DD:EE:FF", "--copies", "100"]
        )
        assert result.exit_code == 0

    # --retry validation tests

    def test_print_retry_below_minimum_rejected(self, runner, mock_image_file):
        """Test --retry=-1 is rejected (minimum is 0)."""
        result = runner.invoke(
            main, ["print", mock_image_file, "--address", "AA:BB:CC:DD:EE:FF", "--retry", "-1"]
        )
        assert result.exit_code != 0
        assert "-1 is not in the range" in result.output or "0<=x<=10" in result.output.replace(
            " ", ""
        )

    def test_print_retry_above_maximum_rejected(self, runner, mock_image_file):
        """Test --retry=11 is rejected (maximum is 10)."""
        result = runner.invoke(
            main, ["print", mock_image_file, "--address", "AA:BB:CC:DD:EE:FF", "--retry", "11"]
        )
        assert result.exit_code != 0
        assert "11" in result.output or "10" in result.output

    def test_print_retry_at_minimum_accepted(self, runner, mock_image_file, monkeypatch):
        """Test --retry=0 is accepted."""
        import p31s.cli

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_image", mock_print)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        result = runner.invoke(
            main, ["print", mock_image_file, "--address", "AA:BB:CC:DD:EE:FF", "--retry", "0"]
        )
        assert result.exit_code == 0

    def test_print_retry_at_maximum_accepted(self, runner, mock_image_file, monkeypatch):
        """Test --retry=10 is accepted."""
        import p31s.cli

        async def mock_connect(self, *args, **kwargs):
            return True

        async def mock_print(self, *args, **kwargs):
            return True

        async def mock_disconnect(self):
            pass

        monkeypatch.setattr(p31s.cli.P31SPrinter, "connect", mock_connect)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "print_image", mock_print)
        monkeypatch.setattr(p31s.cli.P31SPrinter, "disconnect", mock_disconnect)

        result = runner.invoke(
            main, ["print", mock_image_file, "--address", "AA:BB:CC:DD:EE:FF", "--retry", "10"]
        )
        assert result.exit_code == 0

    def test_test_command_retry_above_maximum_rejected(self, runner):
        """Test test command rejects --retry=11."""
        result = runner.invoke(main, ["test", "--address", "AA:BB:CC:DD:EE:FF", "--retry", "11"])
        assert result.exit_code != 0
        assert "11" in result.output or "10" in result.output

    def test_barcode_copies_above_maximum_rejected(self, runner):
        """Test barcode command rejects --copies=101."""
        result = runner.invoke(
            main, ["barcode", "12345", "--address", "AA:BB:CC:DD:EE:FF", "--copies", "101"]
        )
        assert result.exit_code != 0
        assert "101" in result.output or "100" in result.output

    def test_barcode_retry_above_maximum_rejected(self, runner):
        """Test barcode command rejects --retry=11."""
        result = runner.invoke(
            main, ["barcode", "12345", "--address", "AA:BB:CC:DD:EE:FF", "--retry", "11"]
        )
        assert result.exit_code != 0
        assert "11" in result.output or "10" in result.output

    def test_qr_copies_above_maximum_rejected(self, runner):
        """Test qr command rejects --copies=101."""
        result = runner.invoke(
            main, ["qr", "https://example.com", "--address", "AA:BB:CC:DD:EE:FF", "--copies", "101"]
        )
        assert result.exit_code != 0
        assert "101" in result.output or "100" in result.output

    def test_qr_retry_above_maximum_rejected(self, runner):
        """Test qr command rejects --retry=11."""
        result = runner.invoke(
            main, ["qr", "https://example.com", "--address", "AA:BB:CC:DD:EE:FF", "--retry", "11"]
        )
        assert result.exit_code != 0
        assert "11" in result.output or "10" in result.output

    def test_test_coverage_retry_above_maximum_rejected(self, runner):
        """Test test-coverage command rejects --retry=11."""
        result = runner.invoke(
            main, ["test-coverage", "--address", "AA:BB:CC:DD:EE:FF", "--retry", "11"]
        )
        assert result.exit_code != 0
        assert "11" in result.output or "10" in result.output
