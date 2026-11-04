"""Log file and the diagnostics report users attach to bug reports.

Everything here may end up in a public issue, so unit identifiers are masked and the home
directory (which contains the user name) is removed.
"""

import logging
import logging.handlers
import os
import platform
import sys
from dataclasses import asdict
from pathlib import Path
from types import TracebackType
from typing import Final

import platformdirs

from rimlight import __version__
from rimlight.device.registry import SupportedDevice, default_registry

LOG_FILE_NAME: Final = "rimlight.log"
_MAX_LOG_BYTES: Final = 1_000_000
_LOG_BACKUPS: Final = 3
_FORMAT: Final = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_REPORT_LOG_LINES: Final = 200

_log = logging.getLogger(__name__)
_root = logging.getLogger("rimlight")
_handler: logging.Handler | None = None


def default_log_path() -> Path:
    return platformdirs.user_log_path("rimlight", appauthor=False) / LOG_FILE_NAME


def setup_logging(path: Path | None = None, level: int = logging.INFO) -> Path:
    """Log to a rotating file, including crashes that would otherwise vanish in a windowed app."""
    global _handler
    stop_logging()
    path = path or default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=_MAX_LOG_BYTES, backupCount=_LOG_BACKUPS, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter(_FORMAT))
    _root.addHandler(_handler)
    _root.setLevel(level)
    sys.excepthook = _log_uncaught
    _log.info("rimlight %s started on %s", __version__, platform.platform())
    return path


def stop_logging() -> None:
    global _handler
    if _handler is not None:
        _root.removeHandler(_handler)
        _handler.close()
        _handler = None
        sys.excepthook = sys.__excepthook__


def _log_uncaught(
    kind: type[BaseException], value: BaseException, traceback: TracebackType | None
) -> None:
    _log.critical("uncaught exception", exc_info=(kind, value, traceback))
    sys.__excepthook__(kind, value, traceback)


def mask_identifier(value: str, visible: int = 2) -> str:
    """Hide all but the last `visible` characters, e.g. "SN0000000042" -> "**********42"."""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


def device_entry(device: SupportedDevice, *, show_serial: bool = False) -> dict[str, object]:
    """One device as plain data. Unit identifiers are masked unless asked for."""
    info = device.info
    entry: dict[str, object] = {
        "driver": device.driver.id,
        **asdict(info),
        "path": info.path.decode(errors="replace"),
    }
    if not show_serial:
        # The strip reports a unit-specific value in its manufacturer string as well as in the
        # serial number, so both are masked.
        entry["serial_number"] = mask_identifier(info.serial_number)
        entry["manufacturer_string"] = mask_identifier(info.manufacturer_string)
    return entry


def _scrub(text: str) -> str:
    return text.replace(str(Path.home()), "~")


def _recent_log(path: Path, lines: int) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(no log file)"
    return "\n".join(content.splitlines()[-lines:]) or "(empty)"


def _devices_section() -> list[str]:
    try:
        devices = default_registry().find_supported(any_interface=True)
    except OSError as exc:
        return [f"listing devices failed: {exc}"]
    if not devices:
        return ["no supported devices found"]
    return [repr(device_entry(device)) for device in devices]


def collect_report(log_path: Path | None = None) -> str:
    """A text report for bug reports. Read-only: no device is opened."""
    log_path = log_path or default_log_path()
    frozen = bool(getattr(sys, "frozen", False))
    lines = [
        f"rimlight {__version__}{' (frozen build)' if frozen else ''}",
        f"Python {platform.python_version()}",
        f"OS: {platform.platform()}",
        f"Session: {os.environ.get('XDG_SESSION_TYPE', 'n/a')}",
        "",
        "Devices:",
        *_devices_section(),
        "",
        f"Last {_REPORT_LOG_LINES} log lines:",
        _recent_log(log_path, _REPORT_LOG_LINES),
    ]
    return _scrub("\n".join(lines))
