"""Caps how fast frames reach a device (CLAUDE.md, Hardware safety)."""

import time
from collections.abc import Callable
from typing import Final

DEFAULT_MAX_FPS: Final = 60
MAX_ALLOWED_FPS: Final = 60


class RateLimiter:
    """Paces callers to at most `max_fps` calls per second by making them wait.

    Waiting rather than dropping means the last frame always arrives (a static color is a single
    frame), and a caller computing frames in a loop simply produces fewer of them.
    """

    def __init__(
        self,
        max_fps: int = DEFAULT_MAX_FPS,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= max_fps <= MAX_ALLOWED_FPS:
            raise ValueError(f"max_fps must be 1..{MAX_ALLOWED_FPS}, got {max_fps}")
        self._interval = 1.0 / max_fps
        self._clock = clock
        self._sleep = sleep
        self._next_allowed = 0.0

    def wait(self) -> None:
        """Block until the next call is allowed."""
        now = self._clock()
        if now < self._next_allowed:
            self._sleep(self._next_allowed - now)
            now = self._next_allowed
        self._next_allowed = now + self._interval
