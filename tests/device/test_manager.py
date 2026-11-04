import threading
from typing import Any

import pytest
from conftest import hid_entry

from rimlight.device.driver import LedColors, solid
from rimlight.device.drivers.fake import FakeDriver, FakeTransport
from rimlight.device.manager import (
    HEALTH_CHECK_INTERVAL_S,
    RESET_AFTER_S,
    RESET_MIN_INTERVAL_S,
    RESUME_SETTLE_S,
    Connection,
    DeviceManager,
    DeviceState,
    open_first_device,
)
from rimlight.device.registry import default_registry
from rimlight.device.transport import DeviceNotRespondingError, TransportError


class FakeWorld:
    """A device that can be absent, healthy or hung, a clock, and a restart that revives it."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.present = True
        self.hung = False
        self.resets = 0
        self.connects = 0
        self.reset_error: OSError | None = None
        self.states: list[DeviceState] = []
        self.driver: FakeDriver | None = None
        self.transports: list[FakeTransport] = []

    def clock(self) -> float:
        return self.now

    def connect(self) -> Connection:
        self.connects += 1
        if not self.present:
            raise TransportError("no supported device found")
        if self.hung:
            raise DeviceNotRespondingError("no answer")
        transport = FakeTransport()
        transport.open()
        self.driver = FakeDriver(transport, led_count=3)
        self.driver.initialize()
        self.transports.append(transport)
        return Connection(transport, self.driver)

    def hang(self) -> None:
        self.hung = True
        assert self.transports
        self.transports[-1].fail_writes = DeviceNotRespondingError("no answer")

    def reset(self) -> None:
        self.resets += 1
        if self.reset_error is not None:
            raise self.reset_error
        self.hung = False


def _use_transport(monkeypatch: pytest.MonkeyPatch, transport: FakeTransport) -> None:
    def factory(info: object) -> FakeTransport:
        return transport

    monkeypatch.setattr("rimlight.device.manager.HidTransport", factory)


@pytest.fixture
def world() -> FakeWorld:
    return FakeWorld()


def _manager(world: FakeWorld, *, resetter: bool = True) -> DeviceManager:
    return DeviceManager(
        world.connect,
        resetter=world if resetter else None,
        on_state=world.states.append,
        clock=world.clock,
    )


def _run_for(manager: DeviceManager, world: FakeWorld, seconds: float) -> None:
    """Advance the clock, stepping whenever the manager asks to."""
    end = world.now + seconds
    while True:
        wait = manager.step()
        if world.now + wait > end:
            world.now = end
            return
        world.now += max(wait, 0.001)


def _red(led_count: int) -> LedColors:
    return solid((255, 0, 0), led_count)


def test_connects_and_shows_frames(world: FakeWorld) -> None:
    manager = _manager(world)
    manager.show(_red)
    _run_for(manager, world, 1)
    assert manager.state is DeviceState.CONNECTED
    assert world.driver is not None
    assert [f.tolist() for f in world.driver.frames] == [[[255, 0, 0]] * 3]


def test_only_the_newest_waiting_frame_is_shown(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    manager.show(lambda n: solid((1, 1, 1), n))
    manager.show(lambda n: solid((2, 2, 2), n))
    _run_for(manager, world, 1)
    assert world.driver is not None
    assert [f[0].tolist() for f in world.driver.frames] == [[2, 2, 2]]


def test_absent_device_is_retried_with_growing_delays(world: FakeWorld) -> None:
    world.present = False
    manager = _manager(world)
    _run_for(manager, world, 1000)
    assert manager.state is DeviceState.SEARCHING
    assert world.resets == 0  # nothing suggests a hang
    # 1, 2, 5, 10, 30 s, then every 60 s.
    assert world.connects == pytest.approx(6 + 1000 // 60, abs=2)


def test_device_is_picked_up_when_it_appears_and_gets_the_frame(world: FakeWorld) -> None:
    world.present = False
    manager = _manager(world)
    manager.show(_red)
    _run_for(manager, world, 100)
    world.present = True
    _run_for(manager, world, 100)
    assert manager.state is DeviceState.CONNECTED
    assert world.driver is not None
    assert len(world.driver.frames) == 1


def test_healthy_device_is_checked_regularly(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    assert world.driver is not None
    assert world.transports[-1].written == [b"I"]
    _run_for(manager, world, HEALTH_CHECK_INTERVAL_S + 1)
    assert world.transports[-1].written == [b"I", b"Q"]
    assert manager.state is DeviceState.CONNECTED
    assert world.connects == 1


def test_silent_device_is_noticed_by_the_health_check_without_frames(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    world.hang()
    _run_for(manager, world, HEALTH_CHECK_INTERVAL_S + 1)
    assert manager.state is DeviceState.NOT_RESPONDING
    assert world.transports[-1].is_open is False


def test_hung_device_is_restarted_and_gets_its_frame_back(world: FakeWorld) -> None:
    manager = _manager(world)
    manager.show(_red)
    _run_for(manager, world, 1)
    world.hang()
    manager.notify_resume()
    _run_for(manager, world, RESUME_SETTLE_S + RESET_AFTER_S + 30)
    assert world.resets == 1
    assert manager.state is DeviceState.CONNECTED
    assert world.states[-2:] == [DeviceState.NOT_RESPONDING, DeviceState.CONNECTED]
    assert world.driver is not None
    assert [f.tolist() for f in world.driver.frames] == [[[255, 0, 0]] * 3]


def test_recovery_without_a_restart_does_not_restart(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    manager.notify_resume()
    _run_for(manager, world, RESUME_SETTLE_S + 60)
    assert world.resets == 0
    assert manager.state is DeviceState.CONNECTED
    assert world.connects == 1


def test_restart_waits_for_plain_reconnects_first(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    world.hang()
    manager.notify_resume()
    _run_for(manager, world, RESET_AFTER_S - 3)
    assert world.resets == 0


def test_restart_is_not_repeated_too_often(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    world.hang()
    world.reset_error = OSError("task failed")
    manager.notify_resume()
    _run_for(manager, world, RESET_MIN_INTERVAL_S * 2.5)
    assert world.resets == 3
    assert manager.state is DeviceState.NOT_RESPONDING


def test_without_a_resetter_it_keeps_trying_and_recovers_on_replug(world: FakeWorld) -> None:
    manager = _manager(world, resetter=False)
    manager.show(_red)
    _run_for(manager, world, 1)
    world.hang()
    manager.notify_resume()
    _run_for(manager, world, 300)
    assert manager.state is DeviceState.NOT_RESPONDING
    world.hung = False
    _run_for(manager, world, 100)
    assert manager.state is DeviceState.CONNECTED
    assert world.resets == 0


def test_device_gone_after_resume_counts_as_hung(world: FakeWorld) -> None:
    """Seen once: after waking, the device was not even enumerated."""
    manager = _manager(world)
    _run_for(manager, world, 1)
    world.hang()
    world.present = False
    manager.notify_resume()
    _run_for(manager, world, RESUME_SETTLE_S + RESET_AFTER_S + 30)
    assert world.resets == 1


def test_device_already_hung_at_startup_is_restarted(world: FakeWorld) -> None:
    """No resume event here: rimlight started after the device had hung."""
    world.hung = True
    manager = _manager(world)
    manager.show(_red)
    _run_for(manager, world, RESET_AFTER_S + 30)
    assert world.resets == 1
    assert manager.state is DeviceState.CONNECTED
    assert world.driver is not None
    assert len(world.driver.frames) == 1


def test_io_error_looks_like_an_unplug_and_does_not_restart(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    world.transports[-1].fail_writes = TransportError("write failed")
    world.present = False
    _run_for(manager, world, HEALTH_CHECK_INTERVAL_S + 120)
    assert manager.state is DeviceState.SEARCHING
    assert world.resets == 0


def test_invalid_frame_is_dropped_without_losing_the_device(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    manager.show(lambda n: solid((1, 2, 3), n + 1))
    _run_for(manager, world, 1)
    assert manager.state is DeviceState.CONNECTED
    assert world.connects == 1


def test_thread_shows_frames_and_stop_closes_the_device(world: FakeWorld) -> None:
    shown = threading.Event()

    def render(led_count: int) -> LedColors:
        shown.set()
        return solid((1, 2, 3), led_count)

    manager = DeviceManager(world.connect)
    manager.start()
    manager.show(render)
    assert shown.wait(5)
    manager.stop()
    manager.stop()  # idempotent
    assert world.transports[-1].is_open is False


def test_open_first_device_reads_the_count_from_the_device(
    fake_enumeration: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_enumeration.append(hid_entry())
    transport = FakeTransport()
    transport.pending_reads.extend(
        [bytes.fromhex("8300020039"), bytes.fromhex("8300020039")]  # count, then initialize
    )
    _use_transport(monkeypatch, transport)
    connection = open_first_device(default_registry())
    assert connection.driver.led_count == 57


def test_open_first_device_closes_on_failure(
    fake_enumeration: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_enumeration.append(hid_entry())
    transport = FakeTransport()
    _use_transport(monkeypatch, transport)
    with pytest.raises(DeviceNotRespondingError):  # recovery needs to see that it is silent
        open_first_device(default_registry())
    assert transport.is_open is False


def test_open_first_device_without_a_device(fake_enumeration: list[dict[str, Any]]) -> None:
    with pytest.raises(TransportError, match="no supported device"):
        open_first_device(default_registry())
