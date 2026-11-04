import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import hid_entry

from rimlight.cli import main
from rimlight.device.discovery import HidDeviceInfo
from rimlight.device.drivers.fake import FakeTransport
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver
from rimlight.device.transport import DeviceNotRespondingError
from rimlight.diagnostics import (
    LOG_FILE_NAME,
    collect_report,
    default_log_path,
    mask_identifier,
    setup_logging,
    stop_logging,
)

SERIAL = "SN0000000042"
MANUFACTURER = "MFR00000000099"


@pytest.fixture
def log_path(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "logs" / LOG_FILE_NAME
    setup_logging(path)
    yield path
    stop_logging()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_setup_writes_to_the_file_with_timestamps(log_path: Path) -> None:
    logging.getLogger("rimlight.device.test").warning("hello %d", 5)
    text = _read(log_path)
    assert "rimlight.device.test: hello 5" in text
    assert "WARNING" in text
    assert text[:4].isdigit()  # starts with the date


def test_setup_twice_does_not_duplicate_lines(tmp_path: Path, log_path: Path) -> None:
    setup_logging(log_path)
    logging.getLogger("rimlight.x").warning("once")
    assert _read(log_path).count("once") == 1


def test_other_libraries_do_not_end_up_in_the_log(log_path: Path) -> None:
    logging.getLogger("somelib").warning("noise")
    assert "noise" not in _read(log_path)


def test_uncaught_exceptions_are_logged(log_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        sys.excepthook(RuntimeError, exc, exc.__traceback__)
    capsys.readouterr()
    text = _read(log_path)
    assert "uncaught exception" in text
    assert "RuntimeError: boom" in text


def test_stop_restores_the_excepthook(tmp_path: Path) -> None:
    setup_logging(tmp_path / LOG_FILE_NAME)
    assert sys.excepthook is not sys.__excepthook__
    stop_logging()
    assert sys.excepthook is sys.__excepthook__


def test_default_log_path_is_per_user() -> None:
    assert default_log_path().name == LOG_FILE_NAME
    assert "rimlight" in default_log_path().parts


def test_silent_device_is_logged(log_path: Path) -> None:
    transport = FakeTransport()
    transport.open()
    with pytest.raises(DeviceNotRespondingError):
        Strip37FA8202Driver(transport, 57).read_led_count()
    assert "no answer to command 0x03" in _read(log_path)


def test_opening_is_logged_without_identifiers(
    log_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingDevice:
        def open_path(self, path: bytes) -> None:
            raise OSError("access denied")

    from rimlight.device.transport import HidTransport, TransportError

    monkeypatch.setattr("hid.device", FailingDevice)
    info = HidDeviceInfo.from_hidapi(hid_entry(serial_number=SERIAL))
    with pytest.raises(TransportError):
        HidTransport(info).open()
    text = _read(log_path)
    assert "access denied" in text
    assert SERIAL not in text


def test_report_masks_identifiers_and_home(
    log_path: Path, fake_enumeration: list[dict[str, Any]]
) -> None:
    fake_enumeration.append(hid_entry(serial_number=SERIAL, manufacturer_string=MANUFACTURER))
    logging.getLogger("rimlight.x").warning("opened %s", Path.home() / "secret")
    report = collect_report(log_path)
    assert "37fa:8202" in report
    assert SERIAL not in report
    assert MANUFACTURER not in report
    assert mask_identifier(SERIAL) in report
    assert str(Path.home()) not in report
    assert "opened ~" in report


def test_report_without_device_or_log(
    tmp_path: Path, fake_enumeration: list[dict[str, Any]]
) -> None:
    report = collect_report(tmp_path / "missing.log")
    assert "no supported devices found" in report
    assert "(no log file)" in report


def test_report_survives_enumeration_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(vendor_id: int = 0, product_id: int = 0) -> list[dict[str, Any]]:
        raise OSError("hid is broken")

    monkeypatch.setattr("hid.enumerate", fail)
    assert "listing devices failed: hid is broken" in collect_report(tmp_path / "missing.log")


def test_cli_prints_the_report(
    fake_enumeration: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["diagnostics"]) == 0
    assert "no supported devices found" in capsys.readouterr().out
