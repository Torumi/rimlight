"""Protocol and driver tests against byte fixtures extracted from real captures."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from rimlight.device.driver import solid
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver
from rimlight.device.protocol import (
    COMMAND_FRAME,
    COMMAND_LED_COUNT,
    REPORT_SIZE,
    ProtocolError,
    decode_led_count,
    decode_response,
    encode_frame,
    encode_led_count_query,
    encode_message,
)
from rimlight.device.transport import DeviceNotRespondingError, FakeTransport

FIXTURES: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "strip_37fa_8202.json").read_text(encoding="utf-8")
)


def _hex(name: str) -> bytes:
    return bytes.fromhex(FIXTURES[name]["report"])


def _hexes(name: str) -> list[bytes]:
    return [bytes.fromhex(h) for h in FIXTURES[name]["reports"]]


def _driver(led_count: int = 57) -> tuple[Strip37FA8202Driver, FakeTransport]:
    transport = FakeTransport()
    transport.open()
    return Strip37FA8202Driver(transport, led_count), transport


def _without_report_id(transport: FakeTransport) -> list[bytes]:
    assert all(w[0] == 0 and len(w) == REPORT_SIZE + 1 for w in transport.written)
    return [w[1:] for w in transport.written]


def test_led_count_query_matches_capture() -> None:
    assert encode_led_count_query() == [_hex("led_count_request")]


def test_led_count_response_matches_capture() -> None:
    response = decode_response(_hex("led_count_response"))
    assert response.command == COMMAND_LED_COUNT
    assert response.status == 0
    assert decode_led_count(response) == FIXTURES["led_count_response"]["led_count"]


def test_solid_frame_matches_capture() -> None:
    rgb = FIXTURES["frame_solid_red"]["rgb"]
    assert encode_frame(solid((rgb[0], rgb[1], rgb[2]), 57)) == _hexes("frame_solid_red")


def test_mirror_frame_matches_capture() -> None:
    colors = np.array(FIXTURES["frame_mirror"]["rgb_per_led"], dtype=np.uint8)
    assert encode_frame(colors) == _hexes("frame_mirror")


def test_frame_ack_matches_capture() -> None:
    response = decode_response(_hex("frame_ack"))
    assert (response.command, response.status, response.data) == (COMMAND_FRAME, 0, b"")


def test_short_message_is_padded() -> None:
    assert encode_message(0x03) == [b"\x03" + bytes(REPORT_SIZE - 1)]


@pytest.mark.parametrize(
    "report",
    [
        b"",
        b"\x82\x00",
        bytes(REPORT_SIZE),  # seen once as a device disappeared (09 frame 56)
        b"\x03\x00\x00\x00",  # request, not a response
        b"\x82\x00\x00\x00",  # no room for a status
        b"\x82\xff\xff\x00",  # longer than the report
    ],
)
def test_bad_responses_are_rejected(report: bytes) -> None:
    with pytest.raises(ProtocolError):
        decode_response(report)


def test_driver_read_led_count_and_initialize() -> None:
    driver, transport = _driver()
    transport.pending_reads.append(_hex("led_count_response"))
    driver.initialize()
    assert _without_report_id(transport) == [_hex("led_count_request")]


def test_initialize_refuses_a_different_length() -> None:
    driver, transport = _driver(led_count=30)
    transport.pending_reads.append(_hex("led_count_response"))
    with pytest.raises(ProtocolError, match="reports 57 LEDs"):
        driver.initialize()


def test_driver_show_sends_frame_and_waits_for_ack() -> None:
    driver, transport = _driver()
    transport.pending_reads.append(_hex("frame_ack"))
    driver.show(solid((255, 15, 15), 57))
    assert _without_report_id(transport) == _hexes("frame_solid_red")
    assert not transport.pending_reads


def test_missing_ack_means_device_not_responding() -> None:
    """After resume, writes succeed but the device stays silent (capture 08)."""
    driver, transport = _driver()
    with pytest.raises(DeviceNotRespondingError):
        driver.show(solid((0, 0, 0), 57))
    assert len(transport.written) == 3


def test_stale_answers_are_skipped() -> None:
    driver, transport = _driver()
    transport.pending_reads.extend([_hex("led_count_response"), _hex("frame_ack")])
    driver.show(solid((0, 0, 0), 57))
    assert not transport.pending_reads


def test_error_status_is_raised() -> None:
    driver, transport = _driver()
    transport.pending_reads.append(b"\x82\x00\x01\x05")
    with pytest.raises(ProtocolError, match="failed"):
        driver.show(solid((0, 0, 0), 57))


def test_no_brightness_or_power_commands() -> None:
    driver, transport = _driver()
    assert not driver.capabilities.hardware_brightness
    assert not driver.capabilities.hardware_power
    with pytest.raises(NotImplementedError):
        driver.set_brightness(0.5)
    assert transport.written == []
