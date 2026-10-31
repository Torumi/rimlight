"""Shared test helpers."""

from typing import Any

import pytest

from rimlight.device.ids import PRODUCT_ID, USAGE_PAGE, VENDOR_ID


def hid_entry(**overrides: Any) -> dict[str, Any]:
    """An entry shaped like `hid.enumerate()` output, defaulting to the vendor interface."""
    entry: dict[str, Any] = {
        "path": b"\\\\?\\hid#fake#if0",
        "vendor_id": VENDOR_ID,
        "product_id": PRODUCT_ID,
        "serial_number": "",
        "release_number": 0x0102,
        "manufacturer_string": "Test",
        "product_string": "Test Strip",
        "usage_page": USAGE_PAGE,
        "usage": 0x01,
        "interface_number": 0,
    }
    entry.update(overrides)
    return entry


@pytest.fixture
def fake_enumeration(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace `hid.enumerate` with a list the test fills in. Hardware is never touched."""
    entries: list[dict[str, Any]] = []

    def fake_enumerate(vendor_id: int = 0, product_id: int = 0) -> list[dict[str, Any]]:
        return [
            e
            for e in entries
            if (not vendor_id or e["vendor_id"] == vendor_id)
            and (not product_id or e["product_id"] == product_id)
        ]

    monkeypatch.setattr("hid.enumerate", fake_enumerate)
    return entries
