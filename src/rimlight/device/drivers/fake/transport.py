"""In-memory transport for tests."""

from collections import deque

from rimlight.device.transport import Transport, TransportClosedError, TransportError


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
