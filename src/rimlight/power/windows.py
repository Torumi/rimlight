"""Windows sleep and resume events through PowerRegisterSuspendResumeNotification.

Works without a window, so also without Qt and in the headless CLI. The callback runs on a system
thread and has to return quickly. Lock and unlock events are not implemented yet (roadmap A11).
"""

import ctypes
import logging
import sys
from collections.abc import Mapping
from typing import Any, Final

from rimlight.power.events import PowerEvent, PowerEventCallback

_log = logging.getLogger(__name__)

_DEVICE_NOTIFY_CALLBACK: Final = 2
_ERROR_SUCCESS: Final = 0
_PBT_APMSUSPEND: Final = 0x0004
_PBT_APMRESUMESUSPEND: Final = 0x0007
_PBT_APMRESUMEAUTOMATIC: Final = 0x0012

# Windows always sends "automatic" on wake, and "suspend" as well if a user is present.
_EVENTS: Final[Mapping[int, PowerEvent]] = {
    _PBT_APMSUSPEND: PowerEvent.SLEEP,
    _PBT_APMRESUMESUSPEND: PowerEvent.RESUME,
    _PBT_APMRESUMEAUTOMATIC: PowerEvent.RESUME,
}


def event_for(notification: int) -> PowerEvent | None:
    return _EVENTS.get(notification)


class WindowsPowerSource:
    def __init__(self) -> None:
        self._callback: PowerEventCallback | None = None
        self._handle: Any = None
        # ctypes objects Windows keeps pointers to: they must outlive the registration.
        self._native_callback: Any = None
        self._parameters: Any = None

    def _on_notification(self, _context: object, notification: int, _setting: object) -> int:
        event = event_for(notification)
        if event is not None and self._callback is not None:
            _log.info("power event: %s", event.name)
            try:
                self._callback(event)
            except Exception:  # must not propagate into a system thread
                _log.exception("power event callback failed")
        return _ERROR_SUCCESS

    def start(self, callback: PowerEventCallback) -> None:
        if sys.platform != "win32":
            raise OSError("WindowsPowerSource only works on Windows")
        if self._handle is not None:
            return
        from ctypes import wintypes

        callback_type = ctypes.WINFUNCTYPE(
            wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.c_void_p
        )

        class SubscribeParameters(ctypes.Structure):
            _fields_ = (("callback", callback_type), ("context", ctypes.c_void_p))

        powrprof = ctypes.WinDLL("powrprof.dll")
        register = powrprof.PowerRegisterSuspendResumeNotification
        register.argtypes = (
            wintypes.DWORD,
            ctypes.POINTER(SubscribeParameters),
            ctypes.POINTER(wintypes.HANDLE),
        )
        register.restype = wintypes.DWORD

        self._callback = callback
        self._native_callback = callback_type(self._on_notification)
        self._parameters = SubscribeParameters(self._native_callback, None)
        handle = wintypes.HANDLE()
        result = register(
            _DEVICE_NOTIFY_CALLBACK, ctypes.byref(self._parameters), ctypes.byref(handle)
        )
        if result != _ERROR_SUCCESS:
            self._callback = None
            raise OSError(f"PowerRegisterSuspendResumeNotification failed: {result}")
        self._handle = handle

    def stop(self) -> None:
        if sys.platform != "win32":
            return
        handle, self._handle = self._handle, None
        if handle is None:
            return
        from ctypes import wintypes

        unregister = ctypes.WinDLL("powrprof.dll").PowerUnregisterSuspendResumeNotification
        unregister.argtypes = (wintypes.HANDLE,)
        unregister.restype = wintypes.DWORD
        result = unregister(handle)
        if result != _ERROR_SUCCESS:
            _log.warning("PowerUnregisterSuspendResumeNotification failed: %d", result)
        self._callback = None
