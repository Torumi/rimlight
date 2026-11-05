"""Which USB devices the system currently lists, including those without a working driver.

hidapi only sees devices with a working HID driver, so a device that came up under another ID
without a driver (Code 28 on Windows) is invisible to it. This only reads the system's device
list and never opens a device. It keeps vendor and product IDs only: the rest of a device instance
ID can hold a serial number.
"""

import logging
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

_log = logging.getLogger(__name__)

_USB_DEVICE: Final = re.compile(r"^USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})\\", re.IGNORECASE)
_CM_GETIDLIST_FILTER_ENUMERATOR: Final = 0x1
_CM_GETIDLIST_FILTER_PRESENT: Final = 0x100
_CR_SUCCESS: Final = 0x0
_CR_BUFFER_SMALL: Final = 0x1A
_LIST_ATTEMPTS: Final = 3  # the list can grow between asking for its size and reading it


@dataclass(frozen=True, slots=True, order=True)
class UsbId:
    vendor_id: int
    product_id: int

    def __str__(self) -> str:
        return f"{self.vendor_id:04X}:{self.product_id:04X}"


def parse_usb_ids(device_ids: Iterable[str]) -> frozenset[UsbId]:
    """IDs of whole USB devices, from device instance IDs. Single interfaces are skipped."""
    matches = (_USB_DEVICE.match(device_id) for device_id in device_ids)
    return frozenset(UsbId(int(m[1], 16), int(m[2], 16)) for m in matches if m)


def _present_device_ids() -> list[str]:
    """Device instance IDs of the USB devices now present. Raises OSError if the lookup fails."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    cfgmgr32 = ctypes.WinDLL("cfgmgr32")
    get_size = cfgmgr32.CM_Get_Device_ID_List_SizeW
    get_size.argtypes = [ctypes.POINTER(wintypes.ULONG), wintypes.LPCWSTR, wintypes.ULONG]
    get_size.restype = wintypes.DWORD
    get_list = cfgmgr32.CM_Get_Device_ID_ListW
    get_list.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG]
    get_list.restype = wintypes.DWORD

    flags = _CM_GETIDLIST_FILTER_ENUMERATOR | _CM_GETIDLIST_FILTER_PRESENT
    code = _CR_BUFFER_SMALL
    for _ in range(_LIST_ATTEMPTS):
        size = wintypes.ULONG()
        code = get_size(ctypes.byref(size), "USB", flags)
        if code != _CR_SUCCESS:
            break
        buffer = ctypes.create_unicode_buffer(size.value)
        code = get_list("USB", buffer, size.value, flags)
        if code == _CR_SUCCESS:
            return [i for i in ctypes.wstring_at(buffer, size.value).split("\0") if i]
        if code != _CR_BUFFER_SMALL:
            break
    raise OSError(f"could not list USB devices (code {code:#x})")


def present_usb_ids() -> frozenset[UsbId]:
    """USB devices now present. Empty where this is not implemented, or if the lookup fails."""
    try:
        return parse_usb_ids(_present_device_ids())
    except OSError as exc:
        _log.warning("%s", exc)
        return frozenset()
