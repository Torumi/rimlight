"""Pure encode/decode of the 37FA:8202 strip's messages. No I/O.

Spec: docs/protocols/strip_37fa_8202.md.

Requests are `[command, length (u16 big-endian), payload]`, responses
`[command | 0x80, length, status, data]`, where length counts status + data. A message longer
than one report continues in headerless reports; the last report is zero-padded.
"""

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

REPORT_SIZE: Final = 64
_HEADER_SIZE: Final = 3
_RESPONSE_FLAG: Final = 0x80

COMMAND_FRAME: Final = 0x02
COMMAND_LED_COUNT: Final = 0x03

STATUS_OK: Final = 0x00


class ProtocolError(Exception):
    """A report does not follow the spec."""


@dataclass(frozen=True, slots=True)
class Response:
    command: int
    """The request command this answers (without the response flag)."""
    status: int
    data: bytes


def encode_message(command: int, payload: bytes = b"") -> list[bytes]:
    """Split a request into zero-padded 64-byte reports."""
    message = bytes([command]) + len(payload).to_bytes(2, "big") + payload
    return [
        message[i : i + REPORT_SIZE].ljust(REPORT_SIZE, b"\x00")
        for i in range(0, len(message), REPORT_SIZE)
    ]


def encode_led_count_query() -> list[bytes]:
    return encode_message(COMMAND_LED_COUNT)


def encode_frame(rgb: NDArray[np.uint8]) -> list[bytes]:
    """Encode one RGB color per LED, shape (led_count, 3). The device expects G, R, B."""
    return encode_message(COMMAND_FRAME, rgb[:, [1, 0, 2]].tobytes())


def decode_response(report: bytes) -> Response:
    """Decode a single-report response (no captured response needs more than one report)."""
    if len(report) < _HEADER_SIZE + 1:
        raise ProtocolError(f"response too short: {report.hex(' ')}")
    if not report[0] & _RESPONSE_FLAG:
        raise ProtocolError(f"not a response: {report[:8].hex(' ')}")
    length = int.from_bytes(report[1:3], "big")
    if length < 1 or _HEADER_SIZE + length > len(report):
        raise ProtocolError(f"bad response length {length}: {report[:8].hex(' ')}")
    return Response(
        command=report[0] & ~_RESPONSE_FLAG,
        status=report[_HEADER_SIZE],
        data=report[_HEADER_SIZE + 1 : _HEADER_SIZE + length],
    )


def decode_led_count(response: Response) -> int:
    if response.command != COMMAND_LED_COUNT or len(response.data) != 1:
        raise ProtocolError(f"not an LED count response: {response}")
    return response.data[0]
