from typing import Any

from conftest import hid_entry

from rimlight.device.discovery import find_devices


def test_filters_by_usage_page(fake_enumeration: list[dict[str, Any]]) -> None:
    fake_enumeration += [
        hid_entry(path=b"vendor", interface_number=0),
        hid_entry(path=b"consumer", usage_page=0x000C, interface_number=1),
        hid_entry(path=b"other-device", vendor_id=0x1234),
    ]
    assert [d.path for d in find_devices()] == [b"vendor"]
    assert [d.path for d in find_devices(usage_page=None)] == [b"vendor", b"consumer"]


def test_keeps_interfaces_without_reported_usage_page(
    fake_enumeration: list[dict[str, Any]],
) -> None:
    fake_enumeration.append(hid_entry(path=b"unknown", usage_page=0))
    assert [d.path for d in find_devices()] == [b"unknown"]


def test_release_formatting(fake_enumeration: list[dict[str, Any]]) -> None:
    fake_enumeration.append(hid_entry(release_number=0x0102))
    assert find_devices()[0].release_str == "1.02"
