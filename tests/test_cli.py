import json
from typing import Any

import pytest
from conftest import hid_entry

from rimlight.cli import main


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


def test_list_nothing_found(
    fake_enumeration: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["list"]) == 1
    assert "No HID interfaces found" in capsys.readouterr().err
