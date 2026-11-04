"""Driver for the USB HID LED strip 37FA:8202 (see README for compatibility).

Implements docs/protocol.md. Every request is answered by the device, and that answer is the
health signal: after sleep/resume the device can keep accepting writes without processing them,
so a missing answer raises `DeviceNotRespondingError` (docs/protocol.md, Sleep / resume).
"""

import time
from typing import Final

from rimlight.device.driver import DeviceCapabilities, DeviceDriver, DeviceMatch, LedColors
from rimlight.device.ids import PRODUCT_ID, USAGE, USAGE_PAGE, VENDOR_ID
from rimlight.device.protocol import (
    COMMAND_FRAME,
    COMMAND_LED_COUNT,
    REPORT_SIZE,
    STATUS_OK,
    ProtocolError,
    Response,
    decode_led_count,
    decode_response,
    encode_frame,
    encode_led_count_query,
)
from rimlight.device.transport import DeviceNotRespondingError

# The device has no report IDs; hidapi takes a leading 0 in that case.
_NO_REPORT_ID: Final = b"\x00"
# Answers took at most 40 ms in steady state and 503 ms once at app start (captures 01, 02, 07).
RESPONSE_TIMEOUT_MS: Final = 1000


class Strip37FA8202Driver(DeviceDriver):
    id = "37fa:8202"
    match = DeviceMatch(VENDOR_ID, PRODUCT_ID, USAGE_PAGE, USAGE)
    # No device commands exist for brightness or power, so the engine does both in software.
    # 75 LEDs ship with the strip (CLAUDE.md); cut strips report fewer through read_led_count().
    capabilities = DeviceCapabilities(
        reports_led_count=True, default_led_count=75, max_led_count=75
    )

    def initialize(self) -> None:
        """Query the LED count; frames of any other length have never been observed."""
        count = self.read_led_count()
        if count != self.led_count:
            raise ProtocolError(
                f"device reports {count} LEDs but the driver was set up for {self.led_count}; "
                "frames of a different length are not documented in docs/protocol.md"
            )

    def read_led_count(self) -> int:
        return decode_led_count(self._request(encode_led_count_query(), COMMAND_LED_COUNT))

    def _show(self, colors: LedColors) -> None:
        self._request(encode_frame(colors), COMMAND_FRAME)

    def _request(self, reports: list[bytes], command: int) -> Response:
        for report in reports:
            self.transport.write(_NO_REPORT_ID + report)
        return self._await_response(command)

    def _await_response(self, command: int) -> Response:
        """Wait for the answer to `command`, skipping stale answers to earlier requests."""
        deadline = time.monotonic() + RESPONSE_TIMEOUT_MS / 1000
        while (remaining := deadline - time.monotonic()) > 0:
            report = self.transport.read(REPORT_SIZE, timeout_ms=max(1, int(remaining * 1000)))
            if not report:
                break  # the read itself waited until the timeout
            response = decode_response(report)
            if response.command != command:
                continue
            if response.status != STATUS_OK:
                raise ProtocolError(f"command 0x{command:02x} failed: {response}")
            return response
        raise DeviceNotRespondingError(f"no answer to command 0x{command:02x}")
