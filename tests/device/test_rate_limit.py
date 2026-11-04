import pytest

from rimlight.device.driver import solid
from rimlight.device.drivers.fake import FakeDriver, FakeTransport
from rimlight.device.rate_limit import DEFAULT_MAX_FPS, RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _limiter(max_fps: int) -> tuple[RateLimiter, FakeClock]:
    clock = FakeClock()
    return RateLimiter(max_fps, clock=clock, sleep=clock.sleep), clock


def test_first_call_does_not_wait() -> None:
    limiter, clock = _limiter(10)
    limiter.wait()
    assert clock.sleeps == []


def test_fast_calls_are_paced_to_the_cap() -> None:
    limiter, clock = _limiter(10)
    start = clock.now
    for _ in range(11):
        limiter.wait()
    assert clock.now - start == pytest.approx(1.0)  # 10 intervals of 0.1 s


def test_slow_calls_do_not_wait_or_build_up_credit() -> None:
    limiter, clock = _limiter(10)
    limiter.wait()
    clock.now += 5.0
    limiter.wait()
    assert clock.sleeps == []
    limiter.wait()  # the long pause gave no burst allowance
    assert clock.sleeps == [pytest.approx(0.1)]


@pytest.mark.parametrize("max_fps", [0, -1, 61])
def test_cap_is_validated(max_fps: int) -> None:
    with pytest.raises(ValueError, match="max_fps"):
        RateLimiter(max_fps)


def test_default_cap() -> None:
    assert DEFAULT_MAX_FPS == 60


def test_driver_paces_frames_and_delivers_all_of_them() -> None:
    limiter, clock = _limiter(10)
    transport = FakeTransport()
    transport.open()
    driver = FakeDriver(transport, led_count=1, rate_limiter=limiter)
    start = clock.now
    for _ in range(3):
        driver.show(solid((1, 2, 3), 1))
    assert len(transport.written) == 3
    assert clock.now - start == pytest.approx(0.2)


def test_rejected_frames_do_not_use_up_a_slot() -> None:
    limiter, clock = _limiter(10)
    transport = FakeTransport()
    transport.open()
    driver = FakeDriver(transport, led_count=2, rate_limiter=limiter)
    with pytest.raises(ValueError, match="expected uint8"):
        driver.show(solid((1, 2, 3), 1))
    driver.show(solid((1, 2, 3), 2))
    assert clock.sleeps == []
