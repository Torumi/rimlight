"""Device lifecycle: connecting, showing colors, noticing a dead device and recovering it.

One thread owns the transport and the driver; everyone else talks to it through `show` and
`notify_resume`, so the UI never blocks on the device. All decisions are in `step`, which tests
drive directly with a fake clock.

After sleep a device can stay on the bus, accept writes and not process them (see
docs/protocols/strip_37fa_8202.md), so an unanswered request counts as a dead device, and silence
is checked for regularly because a static color sends no frames.
"""

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, Protocol

from rimlight.device.driver import DeviceDriver, LedColors
from rimlight.device.rate_limit import RateLimiter
from rimlight.device.registry import DriverRegistry
from rimlight.device.transport import (
    DeviceNotRespondingError,
    HidTransport,
    Transport,
    TransportError,
)

_log = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL_S: Final = 30.0
# Windows needs a moment after waking before the device is usable again.
RESUME_SETTLE_S: Final = 2.0
RECONNECT_DELAYS_S: Final[Sequence[float]] = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
# Try plain reconnects for this long before restarting the device.
RESET_AFTER_S: Final = 10.0
RESET_MIN_INTERVAL_S: Final = 300.0

type FrameRenderer = Callable[[int], LedColors]
"""Colors for a given LED count; the count is unknown until the device is connected."""


class DeviceState(Enum):
    SEARCHING = auto()
    """No device found, as when it is not plugged in."""
    CONNECTED = auto()
    NOT_RESPONDING = auto()
    """The device was lost in a way that looks like a hang rather than an unplug."""


@dataclass(frozen=True, slots=True)
class Connection:
    transport: Transport
    driver: DeviceDriver


class DeviceResetter(Protocol):
    """Restarts a hung device. Raises OSError if that fails."""

    def reset(self) -> None: ...


type Connector = Callable[[], Connection]
"""Opens and initializes a device. Raises TransportError if there is none or it does not answer."""


def open_first_device(
    registry: DriverRegistry, *, led_count: int | None = None, max_fps: int | None = None
) -> Connection:
    """Connect to the first supported device. `led_count=None` uses what the device reports."""
    found = registry.find_supported()
    if not found:
        raise TransportError("no supported device found")
    device = found[0]
    limiter = RateLimiter(max_fps) if max_fps is not None else None
    transport = HidTransport(device.info)
    transport.open()
    try:
        count = led_count
        if count is None:
            count = _reported_led_count(device.driver, transport)
        driver = device.driver(transport, count, rate_limiter=limiter)
        driver.initialize()
    except TransportError:
        transport.close()
        raise
    except ValueError as exc:
        transport.close()
        raise TransportError(f"cannot initialize device: {exc}") from exc
    return Connection(transport, driver)


def _reported_led_count(driver: type[DeviceDriver], transport: Transport) -> int:
    caps = driver.capabilities
    if caps.reports_led_count:
        count = driver(transport, 1).read_led_count()
        if count is not None:
            return count
    return caps.default_led_count


class DeviceManager:
    def __init__(
        self,
        connect: Connector,
        *,
        resetter: DeviceResetter | None = None,
        on_state: Callable[[DeviceState], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._connect = connect
        self._resetter = resetter
        self._on_state = on_state
        self._clock = clock
        self._state = DeviceState.SEARCHING
        self._state_reported = False
        self._last_failure = ""

        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pending: FrameRenderer | None = None
        self._resumed = False

        # Only touched by the thread running `step`.
        self._connection: Connection | None = None
        self._last_frame: FrameRenderer | None = None
        self._next_attempt = 0.0
        self._delay_index = 0
        self._next_health_check = 0.0
        self._may_be_hung = False
        self._failing_since: float | None = None
        self._last_reset: float | None = None

    @property
    def state(self) -> DeviceState:
        return self._state

    # --- Thread-safe API ---

    def show(self, render: FrameRenderer) -> None:
        """Show this frame as soon as possible, replacing one still waiting. It is shown again
        after every reconnect."""
        with self._lock:
            self._pending = render
        self._wake.set()

    def notify_resume(self) -> None:
        """The computer woke up: check the device soon."""
        with self._lock:
            self._resumed = True
        self._wake.set()

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="device-manager", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the thread and close the device. Must be idempotent."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self._close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                wait = self.step()
            except Exception:  # a bug here must not end recovery for good
                _log.exception("device manager step failed")
                wait = RECONNECT_DELAYS_S[-1]
            self._wake.wait(wait)
            self._wake.clear()

    # --- Decisions ---

    def step(self) -> float:
        """Do one piece of work. Returns the seconds until the next step is due."""
        now = self._clock()
        with self._lock:
            pending, self._pending = self._pending, None
            resumed, self._resumed = self._resumed, False
        if pending is not None:
            self._last_frame = pending
        if resumed:
            self._may_be_hung = True
            self._failing_since = self._failing_since or now
            self._next_health_check = now + RESUME_SETTLE_S
            self._next_attempt = min(self._next_attempt, now + RESUME_SETTLE_S)
        if self._connection is None:
            return self._step_disconnected(now)
        return self._step_connected(now, pending)

    def _step_connected(self, now: float, frame: FrameRenderer | None) -> float:
        assert self._connection is not None
        driver = self._connection.driver
        try:
            if frame is not None:
                self._send(driver, frame)
            elif now >= self._next_health_check:
                driver.read_led_count()
            else:
                return self._next_health_check - now
        except TransportError as exc:
            self._lost(now, exc)
            return 0.0
        self._next_health_check = now + HEALTH_CHECK_INTERVAL_S
        self._may_be_hung = False
        self._failing_since = None
        return HEALTH_CHECK_INTERVAL_S

    def _send(self, driver: DeviceDriver, frame: FrameRenderer) -> None:
        try:
            colors = frame(driver.led_count)
            driver.show(colors)
        except ValueError:  # a bad frame is the caller's bug, not a dead device
            _log.exception("dropped an invalid frame")

    def _lost(self, now: float, exc: TransportError) -> None:
        _log.warning("device lost: %s", exc)
        self._close()
        self._note_failure(now, exc)
        self._next_attempt = now
        self._delay_index = 0
        self._update_lost_state()

    def _note_failure(self, now: float, exc: TransportError) -> None:
        """A silent device looks hung; an I/O error alone looks like an unplug."""
        if isinstance(exc, DeviceNotRespondingError):
            self._may_be_hung = True
        if self._may_be_hung:
            self._failing_since = self._failing_since or now

    def _update_lost_state(self) -> None:
        hung = self._may_be_hung
        self._set_state(DeviceState.NOT_RESPONDING if hung else DeviceState.SEARCHING)

    def _step_disconnected(self, now: float) -> float:
        if now < self._next_attempt:
            return self._next_attempt - now
        try:
            self._connection = self._connect()
        except TransportError as exc:
            if str(exc) != self._last_failure:  # retries go on for hours
                self._last_failure = str(exc)
                _log.info("device not available: %s", exc)
            self._note_failure(now, exc)
            self._maybe_reset(now)
            delay = RECONNECT_DELAYS_S[self._delay_index]
            self._delay_index = min(self._delay_index + 1, len(RECONNECT_DELAYS_S) - 1)
            self._next_attempt = now + delay
            self._update_lost_state()
            return delay
        _log.info("device connected, %d LEDs", self._connection.driver.led_count)
        self._last_failure = ""
        self._delay_index = 0
        self._may_be_hung = False
        self._failing_since = None
        self._next_health_check = now + HEALTH_CHECK_INTERVAL_S
        self._set_state(DeviceState.CONNECTED)
        if self._last_frame is not None:
            with self._lock:
                self._pending = self._pending or self._last_frame
        return 0.0

    def _maybe_reset(self, now: float) -> None:
        if self._resetter is None or not self._may_be_hung or self._failing_since is None:
            return
        if now - self._failing_since < RESET_AFTER_S:
            return
        if self._last_reset is not None and now - self._last_reset < RESET_MIN_INTERVAL_S:
            return
        self._last_reset = now
        _log.warning("device still silent, restarting it")
        try:
            self._resetter.reset()
        except OSError as exc:
            _log.warning("device restart failed: %s", exc)
            return
        self._delay_index = 0

    def _close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            try:
                connection.transport.close()
            except OSError as exc:
                _log.warning("closing the device failed: %s", exc)

    def _set_state(self, state: DeviceState) -> None:
        if state is self._state and self._state_reported:
            return
        self._state = state
        self._state_reported = True
        _log.info("device state: %s", state.name)
        if self._on_state is not None:
            self._on_state(state)
