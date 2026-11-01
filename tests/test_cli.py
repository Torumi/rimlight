import json
from typing import Any

import pytest
from conftest import hid_entry

from rimlight.cli import main, mask_identifier


def test_list_prints_table(
    fake_enumeration: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    fake_enumeration.append(hid_entry(path=b"dev-path", product_string="Strip X"))
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "0xFF00" in out
    assert "Strip X" in out
    assert "dev-path" in out


def test_list_json(
    fake_enumeration: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    fake_enumeration.append(hid_entry(path=b"dev-path"))
    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["path"] == "dev-path"
    assert payload[0]["usage_page"] == 0xFF00
    assert payload[0]["driver"] == "37fa:8202"


def test_list_json_masks_unit_identifiers_by_default(
    fake_enumeration: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    fake_enumeration.append(
        hid_entry(serial_number="SN0000000042", manufacturer_string="MFR00000000099")
    )
    assert main(["list", "--json"]) == 0
    out = capsys.readouterr().out
    assert "SN0000000042" not in out
    assert "MFR00000000099" not in out
    entry = json.loads(out)[0]
    assert entry["serial_number"] == "**********42"
    assert entry["manufacturer_string"] == "************99"


def test_list_json_show_serial(
    fake_enumeration: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    fake_enumeration.append(hid_entry(serial_number="SN0000000042"))
    assert main(["list", "--json", "--show-serial"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["serial_number"] == "SN0000000042"


@pytest.mark.parametrize(
    ("value", "expected"), [("", ""), ("A", "*"), ("AB", "**"), ("ABC", "*BC")]
)
def test_mask_identifier_short_values(value: str, expected: str) -> None:
    assert mask_identifier(value) == expected


def test_list_nothing_found(
    fake_enumeration: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["list"]) == 1
    assert "No supported devices found" in capsys.readouterr().err
