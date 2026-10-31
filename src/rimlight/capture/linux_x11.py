"""Linux X11 capture via XShm. Not implemented yet."""

from rimlight.capture.base import Frame


class X11Capture:
    name = "linux_x11"

    def open(self) -> None:
        raise NotImplementedError

    def grab(self) -> Frame | None:
        raise NotImplementedError

    def close(self) -> None:
        pass
