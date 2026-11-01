"""Driver for the USB HID LED strip 37FA:8202 (see README for compatibility).

The interface is identified from the OS device list (CLAUDE.md, Hardware safety). Everything
that talks to the device waits for docs/protocol.md: until a report is documented there with
the captures it comes from, the methods refuse to send anything.
"""

from rimlight.device.driver import DeviceCapabilities, DeviceDriver, DeviceMatch, LedColors
from rimlight.device.ids import PRODUCT_ID, USAGE, USAGE_PAGE, VENDOR_ID

_PENDING = "not implemented until the report is documented in docs/protocol.md"


class Strip37FA8202Driver(DeviceDriver):
    id = "37fa:8202"
    match = DeviceMatch(VENDOR_ID, PRODUCT_ID, USAGE_PAGE, USAGE)
    # Placeholder until the captures show what the device supports natively (#16, #17, #31).
    # 75 LEDs ship with the strip (CLAUDE.md); the real maximum comes from the protocol.
    capabilities = DeviceCapabilities(default_led_count=75, max_led_count=75)

    def initialize(self) -> None:
        raise NotImplementedError(f"init sequence (#14): {_PENDING}")

    def _show(self, colors: LedColors) -> None:
        raise NotImplementedError(f"color reports (#15, #31): {_PENDING}")
