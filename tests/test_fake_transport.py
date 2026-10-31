import pytest

from rimlight.device.transport import FakeTransport, TransportClosedError, TransportError


def test_records_written_reports() -> None:
    with FakeTransport() as transport:
        assert transport.write(b"\x00\x01\x02") == 3
        transport.write(b"\x00\xff")
    assert transport.written == [b"\x00\x01\x02", b"\x00\xff"]
    assert not transport.is_open


def test_write_when_closed_raises() -> None:
    with pytest.raises(TransportClosedError):
        FakeTransport().write(b"\x00")


def test_injected_write_error_fires_once() -> None:
    transport = FakeTransport()
    transport.open()
    transport.fail_next_write = TransportError("device gone")
    with pytest.raises(TransportError, match="device gone"):
        transport.write(b"\x00")
    transport.write(b"\x01")
    assert transport.written == [b"\x01"]


def test_read_replays_queue_then_times_out() -> None:
    transport = FakeTransport()
    transport.pending_reads.append(b"\x01\x02\x03")
    with transport:
        assert transport.read(2) == b"\x01\x02"
        assert transport.read(64, timeout_ms=10) == b""
