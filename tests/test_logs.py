import logging
import os
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from conftest import hid_entry

from rimlight.device.discovery import HidDeviceInfo
from rimlight.device.drivers.fake import FakeTransport
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver
from rimlight.device.transport import DeviceNotRespondingError, HidTransport, TransportError
from rimlight.logs import (
    default_log_dir,
    latest_log,
    session_log_path,
    setup_logging,
    stop_logging,
)

SERIAL = "SN0000000042"
STARTED = datetime(2026, 11, 4, 18, 5, 9)


@pytest.fixture
def log_path(tmp_path: Path) -> Iterator[Path]:
    yield setup_logging(tmp_path / "logs")
    stop_logging()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_setup_writes_to_the_file_with_timestamps(log_path: Path) -> None:
    logging.getLogger("rimlight.device.test").warning("hello %d", 5)
    text = _read(log_path)
    assert "rimlight.device.test: hello 5" in text
    assert "WARNING" in text
    assert text[:4].isdigit()  # starts with the date


def test_setup_twice_does_not_duplicate_lines(log_path: Path) -> None:
    setup_logging(log_path.parent, now=STARTED)
    logging.getLogger("rimlight.x").warning("once")
    log_path = session_log_path(log_path.parent, STARTED)
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
    setup_logging(tmp_path)
    assert sys.excepthook is not sys.__excepthook__
    stop_logging()
    assert sys.excepthook is sys.__excepthook__


def test_default_log_dir_is_per_user() -> None:
    assert default_log_dir().name == "logs"
    assert "rimlight" in default_log_dir().parts


def test_each_session_gets_its_own_named_file(tmp_path: Path) -> None:
    first = setup_logging(tmp_path, now=STARTED)
    logging.getLogger("rimlight.x").warning("first session")
    second = setup_logging(tmp_path, now=datetime(2026, 11, 5, 9, 0, 0))
    logging.getLogger("rimlight.x").warning("second session")
    stop_logging()
    assert first.name == "rimlight_04.11.26-18.05.09.log"
    assert second.name == "rimlight_05.11.26-09.00.00.log"
    assert "second" not in _read(first)
    assert "first" not in _read(second)


def _touch(directory: Path, name: str, mtime: int) -> Path:
    path = directory / name
    path.write_text("", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_latest_log_goes_by_time_not_name(tmp_path: Path) -> None:
    # By name, 31.10 sorts after 04.11, although it is older.
    _touch(tmp_path, "rimlight_31.10.26-10.00.00.log", 1000)
    newest = _touch(tmp_path, "rimlight_04.11.26-10.00.00.log", 2000)
    _touch(tmp_path, f"{newest.name}.1", 3000)  # a rotated part is not a session
    assert latest_log(tmp_path) == newest


def test_latest_log_without_logs(tmp_path: Path) -> None:
    assert latest_log(tmp_path) is None
    assert latest_log(tmp_path / "missing") is None


def test_only_recent_sessions_are_kept(tmp_path: Path) -> None:
    old = [_touch(tmp_path, f"rimlight_{i:02}.01.26-10.00.00.log", 1000 + i) for i in range(1, 26)]
    rotated = _touch(tmp_path, f"{old[0].name}.1", 1000)
    unrelated = _touch(tmp_path, "notes.txt", 1000)
    current = setup_logging(tmp_path, now=STARTED)
    stop_logging()
    assert current.exists()
    assert unrelated.exists()
    assert not old[0].exists()
    assert not rotated.exists()
    assert old[-1].exists()
    assert len(list(tmp_path.glob("rimlight_*.log"))) == 20


def test_silent_device_is_logged(log_path: Path) -> None:
    transport = FakeTransport()
    transport.open()
    with pytest.raises(DeviceNotRespondingError):
        Strip37FA8202Driver(transport, 57).read_led_count()
    assert "no answer to command 0x03" in _read(log_path)


def test_failed_open_is_logged_without_identifiers(
    log_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingDevice:
        def open_path(self, path: bytes) -> None:
            raise OSError("access denied")

    monkeypatch.setattr("hid.device", FailingDevice)
    info = HidDeviceInfo.from_hidapi(hid_entry(serial_number=SERIAL))
    with pytest.raises(TransportError):
        HidTransport(info).open()
    text = _read(log_path)
    assert "access denied" in text
    assert SERIAL not in text
