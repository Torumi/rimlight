import logging
import threading
from typing import Any

import pytest
from conftest import hid_entry

from rimlight.device.driver import LedColors, solid
from rimlight.device.drivers.fake import FakeDriver, FakeTransport
from rimlight.device.manager import (
    BOOTLOADER_QUICK_RESETS,
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
from rimlight.device.transport import (
    DeviceInBootloaderError,
    DeviceNotRespondingError,
    TransportError,
)
from rimlight.device.usb_nodes import UsbId

BOOTLOADER = UsbId(0x4348, 0x55E0)


class FakeWorld:
    """A device that can be absent, healthy or hung, a clock, and a restart that revives it."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.present = True
        self.hung = False
        self.in_bootloader = False
        self.stuck_in_bootloader = False
        self.reset_enters_bootloader = False
        self.ignored_resets = 0
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
        if self.in_bootloader:
            raise DeviceInBootloaderError("device is in its bootloader")
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
        if self.ignored_resets > 0:
            self.ignored_resets -= 1
            return
        self.hung = False
        self.in_bootloader = self.stuck_in_bootloader or self.reset_enters_bootloader
        self.reset_enters_bootloader = False


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


def test_absent_device_at_start_is_reported_once_with_the_reason(
    world: FakeWorld, caplog: pytest.LogCaptureFixture
) -> None:
    world.present = False
    manager = _manager(world)
    with caplog.at_level(logging.INFO, logger="rimlight.device.manager"):
        _run_for(manager, world, 100)
    assert world.states == [DeviceState.SEARCHING]
    assert caplog.text.count("no supported device found") == 1


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


def test_every_wake_may_restart_the_device_again(world: FakeWorld) -> None:
    """Seen on the strip: two sleeps within a minute, and the second hung it like the first."""
    manager = _manager(world)
    manager.show(_red)
    _run_for(manager, world, 1)
    for expected in (1, 2, 3):
        world.hang()
        manager.notify_resume()
        _run_for(manager, world, RESUME_SETTLE_S + RESET_AFTER_S + 15)
        assert world.resets == expected
        assert manager.state is DeviceState.CONNECTED


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


def test_bootloader_at_start_is_restarted_at_once_and_gets_the_frame(world: FakeWorld) -> None:
    world.in_bootloader = True
    manager = _manager(world)
    manager.show(_red)
    manager.step()
    assert world.resets == 1
    assert manager.state is DeviceState.IN_BOOTLOADER
    _run_for(manager, world, 30)
    assert manager.state is DeviceState.CONNECTED
    assert world.states == [DeviceState.IN_BOOTLOADER, DeviceState.CONNECTED]
    assert world.driver is not None
    assert [f.tolist() for f in world.driver.frames] == [[[255, 0, 0]] * 3]


def test_replug_into_the_bootloader_is_restarted(world: FakeWorld) -> None:
    manager = _manager(world)
    manager.show(_red)
    _run_for(manager, world, 1)
    world.transports[-1].fail_writes = TransportError("write failed")
    world.present = False
    _run_for(manager, world, HEALTH_CHECK_INTERVAL_S + 5)
    assert manager.state is DeviceState.SEARCHING
    assert world.resets == 0
    world.present = True
    world.in_bootloader = True
    _run_for(manager, world, 60)
    assert world.resets == 1
    assert manager.state is DeviceState.CONNECTED
    assert world.driver is not None
    assert len(world.driver.frames) == 1


def test_bootloader_without_a_resetter_is_reported_and_left_alone(world: FakeWorld) -> None:
    world.in_bootloader = True
    manager = _manager(world, resetter=False)
    _run_for(manager, world, 300)
    assert manager.state is DeviceState.IN_BOOTLOADER
    assert world.resets == 0
    world.in_bootloader = False
    _run_for(manager, world, 100)
    assert manager.state is DeviceState.CONNECTED


def test_failed_bootloader_restart_is_not_fatal(world: FakeWorld) -> None:
    world.in_bootloader = True
    world.reset_error = OSError("task failed")
    manager = _manager(world)
    _run_for(manager, world, 5)
    assert world.resets == 1
    assert manager.state is DeviceState.IN_BOOTLOADER


def test_restart_without_effect_is_soon_repeated(world: FakeWorld) -> None:
    """Seen on the strip: right after a replug, the first restart left it in the bootloader."""
    world.in_bootloader = True
    world.ignored_resets = 1
    manager = _manager(world)
    _run_for(manager, world, 20)
    assert world.resets == 2
    assert manager.state is DeviceState.CONNECTED


def test_a_restart_gets_time_to_finish_before_the_next(world: FakeWorld) -> None:
    """Seen on the strip: up to 8 s until it is back under its own ID."""
    world.in_bootloader = True
    world.stuck_in_bootloader = True
    manager = _manager(world)
    _run_for(manager, world, 9)
    assert world.resets == 1


def test_bootloader_restarts_slow_down_if_they_do_not_help(world: FakeWorld) -> None:
    """The ID is the chip maker's, so this may be another device being flashed on purpose."""
    world.in_bootloader = True
    world.stuck_in_bootloader = True
    manager = _manager(world)
    _run_for(manager, world, 200)
    assert world.resets == BOOTLOADER_QUICK_RESETS
    _run_for(manager, world, RESET_MIN_INTERVAL_S)
    assert world.resets == BOOTLOADER_QUICK_RESETS + 1


def test_each_replug_gets_a_quick_restart_again(world: FakeWorld) -> None:
    manager = _manager(world)
    _run_for(manager, world, 1)
    for expected in range(1, BOOTLOADER_QUICK_RESETS + 3):
        world.transports[-1].fail_writes = TransportError("write failed")
        world.in_bootloader = True
        _run_for(manager, world, HEALTH_CHECK_INTERVAL_S + 5)
        assert world.resets == expected
        assert manager.state is DeviceState.CONNECTED


def test_hang_restart_does_not_delay_the_bootloader_restart(world: FakeWorld) -> None:
    """A restart of a hung device can bring it up in the bootloader."""
    manager = _manager(world)
    _run_for(manager, world, 1)
    world.hang()
    world.reset_enters_bootloader = True
    manager.notify_resume()
    _run_for(manager, world, RESUME_SETTLE_S + RESET_AFTER_S + 30)
    assert world.resets == 2
    assert manager.state is DeviceState.CONNECTED


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


def test_open_first_device_never_opens_the_bootloader(
    fake_enumeration: list[dict[str, Any]],
    fake_usb_nodes: set[UsbId],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_transport(info: object) -> FakeTransport:
        pytest.fail("the bootloader must not be opened")

    monkeypatch.setattr("rimlight.device.manager.HidTransport", no_transport)
    fake_usb_nodes.add(BOOTLOADER)
    with pytest.raises(DeviceInBootloaderError):
        open_first_device(default_registry())


def test_open_first_device_prefers_the_device_over_a_bootloader(
    fake_enumeration: list[dict[str, Any]],
    fake_usb_nodes: set[UsbId],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Another device of the same chip maker can be in its bootloader next to a working strip."""
    fake_enumeration.append(hid_entry())
    fake_usb_nodes.add(BOOTLOADER)
    transport = FakeTransport()
    transport.pending_reads.extend([bytes.fromhex("8300020039"), bytes.fromhex("8300020039")])
    _use_transport(monkeypatch, transport)
    assert open_first_device(default_registry()).driver.led_count == 57


def test_open_first_device_without_a_device(fake_enumeration: list[dict[str, Any]]) -> None:
    with pytest.raises(TransportError, match="no supported device"):
        open_first_device(default_registry())
