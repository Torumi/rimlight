"""Logging setup: one log file per session, including crashes a windowed app would otherwise lose.

Logs may be pasted into public issues: never log serial numbers or other unit identifiers.
"""

import logging
import logging.handlers
import platform
import sys
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Final

import platformdirs

from rimlight import __version__

_PREFIX: Final = "rimlight_"
_SUFFIX: Final = ".log"
_TIMESTAMP: Final = "%d.%m.%y-%H.%M.%S"
_KEPT_SESSIONS: Final = 20
# A session can run for weeks, so one session's log still rotates.
_MAX_LOG_BYTES: Final = 1_000_000
_LOG_BACKUPS: Final = 3
_FORMAT: Final = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_log = logging.getLogger(__name__)
_root = logging.getLogger("rimlight")
_handler: logging.Handler | None = None


def default_log_dir() -> Path:
    return platformdirs.user_state_path("rimlight", appauthor=False) / "logs"


def session_log_path(directory: Path, started: datetime) -> Path:
    return directory / f"{_PREFIX}{started.strftime(_TIMESTAMP)}{_SUFFIX}"


def _session_logs(directory: Path) -> list[Path]:
    """Session logs, newest first. By modification time: the names do not sort by date."""
    return sorted(
        directory.glob(f"{_PREFIX}*{_SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True
    )


def latest_log(directory: Path | None = None) -> Path | None:
    logs = _session_logs(directory or default_log_dir())
    return logs[0] if logs else None


def _remove_old_sessions(directory: Path, keep: int = _KEPT_SESSIONS) -> None:
    for old in _session_logs(directory)[keep:]:
        for path in (old, *directory.glob(f"{old.name}.*")):
            try:
                path.unlink()
            except OSError as exc:
                _log.warning("cannot remove old log %s: %s", path.name, exc)


def setup_logging(
    directory: Path | None = None, level: int = logging.INFO, *, now: datetime | None = None
) -> Path:
    """Start this session's log file; messages and uncaught exceptions go there."""
    global _handler
    stop_logging()
    directory = directory or default_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = session_log_path(directory, now or datetime.now())
    _handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=_MAX_LOG_BYTES, backupCount=_LOG_BACKUPS, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter(_FORMAT))
    _root.addHandler(_handler)
    _root.setLevel(level)
    sys.excepthook = _log_uncaught
    _log.info("rimlight %s started on %s", __version__, platform.platform())
    _remove_old_sessions(directory)
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
