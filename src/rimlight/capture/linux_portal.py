"""Linux Wayland capture via xdg-desktop-portal ScreenCast + PipeWire. Not implemented yet."""

from rimlight.capture.base import Frame


class PortalCapture:
    name = "linux_portal"

    def open(self) -> None:
        raise NotImplementedError

    def grab(self) -> Frame | None:
        raise NotImplementedError

    def close(self) -> None:
        pass
