"""Test doubles for everything above the device layer. Never a built-in driver."""

from rimlight.device.drivers.fake.driver import FakeDriver
from rimlight.device.drivers.fake.transport import FakeTransport

__all__ = ["FakeDriver", "FakeTransport"]
