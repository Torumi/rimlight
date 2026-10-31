"""Read-only checks against the real strip. Run manually: `uv run pytest -m hardware`."""

import pytest

from rimlight.device.discovery import find_devices
from rimlight.device.transport import HidTransport


@pytest.mark.hardware
def test_strip_is_enumerated() -> None:
    assert find_devices(), "strip not found; is it plugged in?"


@pytest.mark.hardware
def test_vendor_interface_opens_and_closes() -> None:
    """Opens the handle and closes it again. Nothing is sent to the device."""
    with HidTransport(find_devices()[0]) as transport:
        assert transport.is_open
    assert not transport.is_open
