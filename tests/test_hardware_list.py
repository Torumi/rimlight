"""Checks against the real strip. Close the vendor app, then run: `uv run pytest -m hardware`.

These send only what docs/protocol.md documents: 0x03 (LED count) and 0x02 (color frame).
"""

import pytest

from rimlight.device.discovery import find_devices
from rimlight.device.driver import solid
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver
from rimlight.device.transport import HidTransport


@pytest.mark.hardware
def test_strip_is_enumerated() -> None:
    assert find_devices(), "strip not found; is it plugged in?"


@pytest.mark.hardware
def test_vendor_interface_opens_and_closes() -> None:
    with HidTransport(find_devices()[0]) as transport:
        assert transport.is_open
    assert not transport.is_open


@pytest.mark.hardware
def test_device_answers_led_count_and_frames() -> None:
    with HidTransport(find_devices()[0]) as transport:
        count = Strip37FA8202Driver(transport, 1).read_led_count()
        assert 1 <= count <= Strip37FA8202Driver.capabilities.max_led_count
        driver = Strip37FA8202Driver(transport, count)
        driver.initialize()
        driver.show(solid((0, 0, 0), count))
