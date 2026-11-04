import logging
import sys

import pytest

from rimlight.power.events import PowerEvent
from rimlight.power.factory import create_power_source
from rimlight.power.windows import WindowsPowerSource, event_for

SUSPEND = 0x0004
RESUME_USER = 0x0007
RESUME_AUTOMATIC = 0x0012
BATTERY_LOW = 0x0009


@pytest.mark.parametrize(
    ("notification", "expected"),
    [
        (SUSPEND, PowerEvent.SLEEP),
        (RESUME_USER, PowerEvent.RESUME),
        (RESUME_AUTOMATIC, PowerEvent.RESUME),
        (BATTERY_LOW, None),
    ],
)
def test_event_for(notification: int, expected: PowerEvent | None) -> None:
    assert event_for(notification) == expected


def _source_with(events: list[PowerEvent]) -> WindowsPowerSource:
    source = WindowsPowerSource()
    source._callback = events.append  # pyright: ignore[reportPrivateUsage]
    return source


def test_notifications_reach_the_callback() -> None:
    events: list[PowerEvent] = []
    source = _source_with(events)
    notify = source._on_notification  # pyright: ignore[reportPrivateUsage]
    assert notify(None, SUSPEND, None) == 0
    assert notify(None, BATTERY_LOW, None) == 0
    assert notify(None, RESUME_AUTOMATIC, None) == 0
    assert events == [PowerEvent.SLEEP, PowerEvent.RESUME]


def test_failing_callback_does_not_reach_the_system_thread(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(_event: PowerEvent) -> None:
        raise RuntimeError("boom")

    source = WindowsPowerSource()
    source._callback = fail  # pyright: ignore[reportPrivateUsage]
    with caplog.at_level(logging.ERROR):
        result = source._on_notification(  # pyright: ignore[reportPrivateUsage]
            None, SUSPEND, None
        )
    assert result == 0
    assert "callback failed" in caplog.text


def test_stop_without_start_is_harmless() -> None:
    WindowsPowerSource().stop()


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows registration")
def test_real_registration_works_without_elevation_and_stops_cleanly() -> None:
    source = create_power_source()
    assert isinstance(source, WindowsPowerSource)
    source.start(lambda _event: None)
    source.start(lambda _event: None)  # idempotent
    source.stop()
    source.stop()  # idempotent


@pytest.mark.skipif(sys.platform == "win32", reason="the other platforms")
def test_start_fails_clearly_on_other_platforms() -> None:
    with pytest.raises(OSError, match="only works on Windows"):
        WindowsPowerSource().start(lambda _event: None)
