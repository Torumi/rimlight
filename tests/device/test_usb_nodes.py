import logging
import sys

import pytest

from rimlight.device.usb_nodes import UsbId, parse_usb_ids, present_usb_ids


def test_keeps_only_vendor_and_product_ids() -> None:
    ids = parse_usb_ids(
        ["USB\\VID_4348&PID_55E0\\SN0000000042", "USB\\vid_37fa&pid_8202\\7&1a&0&2"]
    )
    assert ids == {UsbId(0x4348, 0x55E0), UsbId(0x37FA, 0x8202)}


@pytest.mark.parametrize(
    "device_id",
    [
        "USB\\ROOT_HUB30\\4&1&0&0",
        "USB\\VID_046D&PID_C53F&MI_00\\7&1&0&0000",  # one interface, not the device
        "HID\\VID_37FA&PID_8202\\7&1&0&0000",
        "",
    ],
)
def test_ignores_everything_but_whole_usb_devices(device_id: str) -> None:
    assert parse_usb_ids([device_id]) == frozenset()


def test_a_failed_lookup_reads_as_nothing_found(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def fail() -> list[str]:
        raise OSError("code 3")

    monkeypatch.setattr("rimlight.device.usb_nodes._present_device_ids", fail)
    with caplog.at_level(logging.WARNING):
        assert present_usb_ids() == frozenset()
    assert "code 3" in caplog.text


@pytest.mark.skipif(sys.platform != "win32", reason="the list comes from Windows")
def test_windows_lists_usb_devices_without_failing(caplog: pytest.LogCaptureFixture) -> None:
    """Read-only. What is plugged in depends on the machine, so only the call is checked."""
    with caplog.at_level(logging.WARNING):
        assert isinstance(present_usb_ids(), frozenset)
    assert not caplog.text


@pytest.mark.skipif(sys.platform == "win32", reason="not implemented elsewhere yet")
def test_other_systems_find_nothing_yet() -> None:
    assert present_usb_ids() == frozenset()
