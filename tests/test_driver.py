from typing import Any

import numpy as np
import pytest
from conftest import hid_entry

from rimlight.device.discovery import HidDeviceInfo
from rimlight.device.driver import DeviceMatch, solid
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver
from rimlight.device.fake import FakeDriver
from rimlight.device.ids import PRODUCT_ID, USAGE, USAGE_PAGE, VENDOR_ID
from rimlight.device.registry import DriverRegistry, default_registry
from rimlight.device.transport import FakeTransport, TransportError


def _info(**overrides: Any) -> HidDeviceInfo:
    return HidDeviceInfo.from_hidapi(hid_entry(**overrides))


def test_match_by_ids_and_usage_page() -> None:
    match = DeviceMatch(VENDOR_ID, PRODUCT_ID, USAGE_PAGE, USAGE)
    assert match.matches(_info())
    assert match.matches(_info(usage_page=0, usage=0))  # backend could not report usage
    assert not match.matches(_info(usage_page=0x000C))
    assert not match.matches(_info(product_id=0x1234))


def test_solid_colors() -> None:
    colors = solid((255, 0, 10), 3)
    assert colors.dtype == np.uint8
    assert colors.tolist() == [[255, 0, 10]] * 3


def test_fake_driver_writes_through_transport() -> None:
    transport = FakeTransport()
    transport.open()
    driver = FakeDriver(transport, led_count=2)
    driver.initialize()
    driver.show(solid((1, 2, 3), 2))
    driver.set_brightness(1.0)
    driver.set_power(False)
    assert transport.written == [b"I", b"C\x01\x02\x03\x01\x02\x03", b"B\xff", b"P\x00"]
    assert driver.initialized == 1
    assert driver.power == [False]


def test_transport_errors_reach_the_caller() -> None:
    transport = FakeTransport()
    transport.open()
    transport.fail_next_write = TransportError("gone")
    with pytest.raises(TransportError):
        FakeDriver(transport, led_count=1).initialize()


@pytest.mark.parametrize("led_count", [0, 301])
def test_led_count_is_validated(led_count: int) -> None:
    with pytest.raises(ValueError, match="led_count"):
        FakeDriver(FakeTransport(), led_count)


@pytest.mark.parametrize(
    "colors",
    [np.zeros((3, 3), np.uint8), np.zeros((2, 4), np.uint8), np.zeros((2, 3), np.int32)],
)
def test_show_rejects_wrong_shape_or_dtype(colors: Any) -> None:
    with pytest.raises(ValueError, match="expected uint8 colors"):
        FakeDriver(FakeTransport(), led_count=2).show(colors)


def test_strip_driver_sends_nothing_until_protocol_is_documented() -> None:
    transport = FakeTransport()
    transport.open()
    driver = Strip37FA8202Driver(transport, led_count=75)
    with pytest.raises(NotImplementedError, match="protocol"):
        driver.initialize()
    with pytest.raises(NotImplementedError, match="protocol"):
        driver.show(solid((0, 0, 0), 75))
    with pytest.raises(NotImplementedError):
        driver.set_brightness(0.5)
    assert transport.written == []


def test_registry_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        DriverRegistry([FakeDriver, FakeDriver])


def test_default_registry_has_the_strip_but_not_the_fake() -> None:
    registry = default_registry()
    assert registry.by_id("37fa:8202") is Strip37FA8202Driver
    assert registry.by_id("fake") is None
    assert registry.driver_for(_info()) is Strip37FA8202Driver


def test_find_supported(fake_enumeration: list[dict[str, Any]]) -> None:
    fake_enumeration += [
        hid_entry(path=b"vendor", interface_number=0),
        hid_entry(path=b"consumer", usage_page=0x000C, usage=0x01, interface_number=1),
        hid_entry(path=b"other", vendor_id=0x1234),
    ]
    registry = default_registry()
    assert [s.info.path for s in registry.find_supported()] == [b"vendor"]
    found = registry.find_supported(any_interface=True)
    assert [s.info.path for s in found] == [b"vendor", b"consumer"]
    assert {s.driver for s in found} == {Strip37FA8202Driver}
