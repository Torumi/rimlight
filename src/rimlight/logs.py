"""Logging setup: a rotating log file, including crashes a windowed app would otherwise lose.

Logs may be pasted into public issues: never log serial numbers or other unit identifiers.
"""

import logging
import logging.handlers
import platform
import sys
from pathlib import Path
from types import TracebackType
from typing import Final

import platformdirs

from rimlight import __version__

LOG_FILE_NAME: Final = "rimlight.log"
_MAX_LOG_BYTES: Final = 1_000_000
_LOG_BACKUPS: Final = 3
_FORMAT: Final = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

_log = logging.getLogger(__name__)
_root = logging.getLogger("rimlight")
_handler: logging.Handler | None = None


def default_log_path() -> Path:
    return platformdirs.user_log_path("rimlight", appauthor=False) / LOG_FILE_NAME


def setup_logging(path: Path | None = None, level: int = logging.INFO) -> Path:
    """Log rimlight's messages and uncaught exceptions to a rotating file."""
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
