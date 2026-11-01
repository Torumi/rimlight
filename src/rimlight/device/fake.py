"""In-memory driver for tests of everything above the device layer."""

from rimlight.device.driver import DeviceCapabilities, DeviceDriver, DeviceMatch, LedColors
from rimlight.device.transport import Transport


class FakeDriver(DeviceDriver):
    """Records what the engine asks for and writes made-up reports to its transport.

    The reports (`b"I"`, `b"C" + colors`, `b"B" + level`, `b"P" + on`) are not any real
    device's protocol; they only let tests exercise transport behaviour such as errors.
    Never registered as a built-in driver.
    """

    id = "fake"
    match = DeviceMatch(vendor_id=0xFFFF, product_id=0xFFFF)
    capabilities = DeviceCapabilities(
        hardware_brightness=True,
        hardware_power=True,
        reports_led_count=True,
        default_led_count=30,
        max_led_count=300,
    )

    def __init__(self, transport: Transport, led_count: int) -> None:
        super().__init__(transport, led_count)
        self.initialized = 0
        self.frames: list[LedColors] = []
        self.brightness: list[float] = []
        self.power: list[bool] = []

    def initialize(self) -> None:
        self.transport.write(b"I")
        self.initialized += 1

    def _show(self, colors: LedColors) -> None:
        self.transport.write(b"C" + colors.tobytes())
        self.frames.append(colors.copy())

    def set_brightness(self, level: float) -> None:
        if not 0.0 <= level <= 1.0:
            raise ValueError(f"brightness must be 0.0-1.0, got {level}")
        self.transport.write(b"B" + bytes([round(level * 255)]))
        self.brightness.append(level)

    def set_power(self, on: bool) -> None:
        self.transport.write(b"P" + bytes([on]))
        self.power.append(on)

    def read_led_count(self) -> int:
        return self.led_count
