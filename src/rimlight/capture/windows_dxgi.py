"""Windows capture via DXGI Desktop Duplication. Not implemented yet."""

from rimlight.capture.base import Frame


class DxgiCapture:
    name = "windows_dxgi"

    def open(self) -> None:
        raise NotImplementedError

    def grab(self) -> Frame | None:
        raise NotImplementedError

    def close(self) -> None:
        pass
