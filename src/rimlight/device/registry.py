"""Maps HID interfaces to the drivers that handle them."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from rimlight.device.discovery import EnumerateFn, HidDeviceInfo, find_devices, hid_enumerate
from rimlight.device.driver import DeviceDriver
from rimlight.device.drivers import BUILTIN_DRIVERS


@dataclass(frozen=True, slots=True)
class SupportedDevice:
    info: HidDeviceInfo
    driver: type[DeviceDriver]


class DriverRegistry:
    def __init__(self, drivers: Iterable[type[DeviceDriver]]) -> None:
        self._drivers: tuple[type[DeviceDriver], ...] = tuple(drivers)
        ids = [d.id for d in self._drivers]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate driver ids: {ids}")

    @property
    def drivers(self) -> Sequence[type[DeviceDriver]]:
        return self._drivers

    def driver_for(self, info: HidDeviceInfo) -> type[DeviceDriver] | None:
        return next((d for d in self._drivers if d.match.matches(info)), None)

    def by_id(self, driver_id: str) -> type[DeviceDriver] | None:
        return next((d for d in self._drivers if d.id == driver_id), None)

    def find_supported(
        self, *, any_interface: bool = False, enumerate_fn: EnumerateFn = hid_enumerate
    ) -> list[SupportedDevice]:
        """Supported devices that are plugged in. Read-only: nothing is opened.

        With `any_interface`, every HID interface of a supported device is listed, not only the
        ones the driver uses (useful for diagnostics).
        """
        found: list[SupportedDevice] = []
        for driver in self._drivers:
            m = driver.match
            usage_page = None if any_interface else m.usage_page
            for info in find_devices(
                m.vendor_id, m.product_id, usage_page, enumerate_fn=enumerate_fn
            ):
                if any_interface or driver.match.matches(info):
                    found.append(SupportedDevice(info, driver))
        return found


def default_registry() -> DriverRegistry:
    return DriverRegistry(BUILTIN_DRIVERS)
