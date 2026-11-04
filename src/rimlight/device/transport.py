"""Transport abstraction. Everything above this layer runs against `FakeTransport` in tests."""

from abc import ABC, abstractmethod
from collections import deque
from types import TracebackType
from typing import TYPE_CHECKING, Self

from rimlight.device.discovery import HidDeviceInfo

if TYPE_CHECKING:
    import hid


class TransportError(OSError):
    """I/O failure on the transport; the caller should close and reopen."""


class TransportClosedError(TransportError):
    """Operation attempted on a transport that is not open."""


class DeviceNotRespondingError(TransportError):
    """The device did not answer in time, even if writes still succeed."""


class Transport(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None:
        """Release the handle. Must be idempotent."""

    @property
    @abstractmethod
    def is_open(self) -> bool: ...

    @abstractmethod
    def write(self, report: bytes) -> int:
        """Send one report (first byte is the report ID). Returns bytes written."""

    @abstractmethod
    def read(self, size: int, timeout_ms: int = 0) -> bytes:
        """Read one input report; empty bytes on timeout."""

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class FakeTransport(Transport):
    """In-memory transport that records written reports and replays queued input reports."""

    def __init__(self) -> None:
        self.written: list[bytes] = []
        self.pending_reads: deque[bytes] = deque()
        self.fail_next_write: TransportError | None = None
        self.open_count = 0
        self._open = False

    def open(self) -> None:
        self._open = True
        self.open_count += 1

    def close(self) -> None:
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def write(self, report: bytes) -> int:
        self._require_open()
        if self.fail_next_write is not None:
            error, self.fail_next_write = self.fail_next_write, None
            raise error
        self.written.append(bytes(report))
        return len(report)

    def read(self, size: int, timeout_ms: int = 0) -> bytes:
        self._require_open()
        return self.pending_reads.popleft()[:size] if self.pending_reads else b""

    def _require_open(self) -> None:
        if not self._open:
            raise TransportClosedError("transport is not open")


class HidTransport(Transport):
    """HID transport via hidapi. Drivers decide what is sent, per docs/protocol.md."""

    def __init__(self, info: HidDeviceInfo) -> None:
        self.info = info
        self._device: hid.device | None = None

    def open(self) -> None:
        if self._device is not None:
            return
        import hid

        device = hid.device()
        try:
            device.open_path(self.info.path)
        except OSError as exc:
            raise TransportError(f"cannot open {self.info.path!r}: {exc}") from exc
        self._device = device

    def close(self) -> None:
        device, self._device = self._device, None
        if device is not None:
            device.close()

    @property
    def is_open(self) -> bool:
        return self._device is not None

    def write(self, report: bytes) -> int:
        device = self._require_device()
        try:
            written = device.write(report)
        except (OSError, ValueError) as exc:
            raise TransportError(f"write failed: {exc}") from exc
        if written < 0:
            raise TransportError("write failed")
        return written

    def read(self, size: int, timeout_ms: int = 0) -> bytes:
        device = self._require_device()
        try:
            # hidapi treats a timeout of 0 as "block forever", ours means "do not wait long".
            return bytes(device.read(size, max(1, timeout_ms)))
        except (OSError, ValueError) as exc:
            raise TransportError(f"read failed: {exc}") from exc

    def _require_device(self) -> "hid.device":
        if self._device is None:
            raise TransportClosedError("transport is not open")
        return self._device
