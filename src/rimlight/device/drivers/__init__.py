"""Built-in device drivers. Adding a device = adding a module here and listing its driver."""

from rimlight.device.driver import DeviceDriver
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver

BUILTIN_DRIVERS: tuple[type[DeviceDriver], ...] = (Strip37FA8202Driver,)

__all__ = ["BUILTIN_DRIVERS"]
