"""Read-only enumeration of matching HID interfaces."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from rimlight.device.ids import PRODUCT_ID, USAGE_PAGE, VENDOR_ID

type EnumerateFn = Callable[[int, int], list[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class HidDeviceInfo:
    path: bytes
    vendor_id: int
    product_id: int
    usage_page: int
    usage: int
    interface_number: int
    product_string: str
    manufacturer_string: str
    serial_number: str
    release_number: int

    @classmethod
    def from_hidapi(cls, raw: Mapping[str, Any]) -> "HidDeviceInfo":
        return cls(
            path=bytes(raw.get("path") or b""),
            vendor_id=int(raw.get("vendor_id") or 0),
            product_id=int(raw.get("product_id") or 0),
            usage_page=int(raw.get("usage_page") or 0),
            usage=int(raw.get("usage") or 0),
            interface_number=int(raw.get("interface_number", -1)),
            product_string=str(raw.get("product_string") or ""),
            manufacturer_string=str(raw.get("manufacturer_string") or ""),
            serial_number=str(raw.get("serial_number") or ""),
            release_number=int(raw.get("release_number") or 0),
        )

    @property
    def release_str(self) -> str:
        """`bcdDevice` as `major.minor`, e.g. 0x0102 -> "1.02"."""
        return f"{self.release_number >> 8:x}.{self.release_number & 0xFF:02x}"


def _hid_enumerate(vendor_id: int, product_id: int) -> list[dict[str, Any]]:
    import hid

    return hid.enumerate(vendor_id, product_id)


def find_devices(
    vendor_id: int = VENDOR_ID,
    product_id: int = PRODUCT_ID,
    usage_page: int | None = USAGE_PAGE,
    *,
    enumerate_fn: EnumerateFn = _hid_enumerate,
) -> list[HidDeviceInfo]:
    """List HID interfaces matching VID/PID and, if given, the usage page.

    A usage page of 0 means the backend could not report it; such interfaces are kept
    rather than silently dropped. Never opens a device.
    """
    found = [HidDeviceInfo.from_hidapi(raw) for raw in enumerate_fn(vendor_id, product_id)]
    matching = [
        d
        for d in found
        if d.vendor_id == vendor_id
        and d.product_id == product_id
        and (usage_page is None or d.usage_page in (usage_page, 0))
    ]
    return sorted(matching, key=lambda d: (d.interface_number, d.path))
