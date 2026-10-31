"""Capture backend interface."""

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

type Frame = NDArray[np.uint8]
"""One captured screen image, shape (height, width, 3), RGB."""


class CaptureUnavailableError(RuntimeError):
    """No capture backend can work in the current session."""


class CaptureBackend(Protocol):
    name: str

    def open(self) -> None:
        """Acquire capture resources (may prompt the user, e.g. the Wayland portal)."""
        ...

    def grab(self) -> Frame | None:
        """Return the latest frame, or None if the screen has not changed."""
        ...

    def close(self) -> None:
        """Release capture resources. Must be idempotent."""
        ...
