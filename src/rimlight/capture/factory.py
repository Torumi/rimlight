"""Pick and construct the capture backend for the running platform."""

import os
import sys
from collections.abc import Mapping
from typing import Literal

from rimlight.capture.base import CaptureBackend, CaptureUnavailableError

type BackendName = Literal["windows_dxgi", "linux_x11", "linux_portal"]


def select_backend_name(platform: str, env: Mapping[str, str]) -> BackendName:
    if platform == "win32":
        return "windows_dxgi"
    if platform.startswith("linux"):
        if env.get("XDG_SESSION_TYPE") == "wayland" or env.get("WAYLAND_DISPLAY"):
            return "linux_portal"
        if env.get("DISPLAY"):
            return "linux_x11"
        raise CaptureUnavailableError("no graphical session (neither Wayland nor X11) found")
    raise CaptureUnavailableError(f"unsupported platform: {platform}")


def create_capture_backend(name: BackendName | None = None) -> CaptureBackend:
    """Construct a backend, importing only the selected platform module."""
    name = name or select_backend_name(sys.platform, os.environ)
    match name:
        case "windows_dxgi":
            from rimlight.capture.windows_dxgi import DxgiCapture

            return DxgiCapture()
        case "linux_x11":
            from rimlight.capture.linux_x11 import X11Capture

            return X11Capture()
        case "linux_portal":
            from rimlight.capture.linux_portal import PortalCapture

            return PortalCapture()
