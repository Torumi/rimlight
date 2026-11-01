"""Device driver interface.

A driver turns generic requests (show these LED colors, set brightness, power) into the reports
of one device family, as documented in docs/protocol.md, and sends them through a `Transport`.
Everything above this layer (engine, UI, CLI) talks to drivers only, so supporting another
device means adding a driver, not changing the engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from rimlight.device.discovery import HidDeviceInfo
from rimlight.device.transport import Transport

type LedColors = NDArray[np.uint8]
"""One RGB color per LED, shape (led_count, 3), in strip order."""


@dataclass(frozen=True, slots=True)
class DeviceMatch:
    """Which HID interface a driver handles. `usage_page=None` accepts any interface."""

    vendor_id: int
    product_id: int
    usage_page: int | None = None
    usage: int | None = None

    def matches(self, info: HidDeviceInfo) -> bool:
        if (info.vendor_id, info.product_id) != (self.vendor_id, self.product_id):
            return False
        # Some HID backends cannot report usage pages (0); keep such interfaces.
        if self.usage_page is not None and info.usage_page not in (self.usage_page, 0):
            return False
        return self.usage is None or info.usage in (self.usage, 0)


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    """What the device does natively; the engine emulates the rest in software."""

    hardware_brightness: bool = False
    """Device has its own brightness control; otherwise the engine scales colors."""
    hardware_power: bool = False
    """Device has an on/off command; otherwise the engine shows black."""
    reports_led_count: bool = False
    """`read_led_count()` returns the attached LED count."""
    default_led_count: int = 1
    max_led_count: int = 1


class DeviceDriver(ABC):
    """Base class for device drivers. Instances are bound to one opened transport."""

    id: ClassVar[str]
    """Stable identifier used in settings, e.g. "37fa:8202"."""
    match: ClassVar[DeviceMatch]
    capabilities: ClassVar[DeviceCapabilities]

    def __init__(self, transport: Transport, led_count: int) -> None:
        caps = self.capabilities
        if not 1 <= led_count <= caps.max_led_count:
            raise ValueError(f"led_count must be 1..{caps.max_led_count}, got {led_count}")
        self.transport = transport
        self.led_count = led_count

    @abstractmethod
    def initialize(self) -> None:
        """Send whatever the device needs after every open, before it accepts colors."""

    def show(self, colors: LedColors) -> None:
        """Display one color per LED."""
        if colors.dtype != np.uint8 or colors.shape != (self.led_count, 3):
            raise ValueError(
                f"expected uint8 colors of shape ({self.led_count}, 3), "
                f"got {colors.dtype} {colors.shape}"
            )
        self._show(colors)

    @abstractmethod
    def _show(self, colors: LedColors) -> None:
        """Encode and send `colors` (already validated)."""

    def set_brightness(self, level: float) -> None:
        """Set hardware brightness, 0.0-1.0. Only called if `hardware_brightness`."""
        raise NotImplementedError(f"{self.id} has no hardware brightness")

    def set_power(self, on: bool) -> None:
        """Switch the device on or off. Only called if `hardware_power`."""
        raise NotImplementedError(f"{self.id} has no power command")

    def read_led_count(self) -> int | None:
        """Attached LED count, if `reports_led_count`; None otherwise."""
        return None


def solid(color: tuple[int, int, int], led_count: int) -> LedColors:
    """All LEDs set to one RGB color."""
    return np.tile(np.array(color, dtype=np.uint8), (led_count, 1))
