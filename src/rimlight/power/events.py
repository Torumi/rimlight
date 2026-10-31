"""Power event interface."""

from collections.abc import Callable
from enum import Enum, auto
from typing import Protocol


class PowerEvent(Enum):
    SLEEP = auto()
    RESUME = auto()
    LOCK = auto()
    UNLOCK = auto()


type PowerEventCallback = Callable[[PowerEvent], None]


class PowerEventSource(Protocol):
    """Delivers power events to a callback, possibly from a background thread."""

    def start(self, callback: PowerEventCallback) -> None: ...

    def stop(self) -> None:
        """Stop listening. Must be idempotent."""
        ...
