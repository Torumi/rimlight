import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import hid_entry

from rimlight.cli import main
from rimlight.diagnostics import collect_report, mask_identifier
from rimlight.logs import setup_logging, stop_logging

SERIAL = "SN0000000042"
MANUFACTURER = "MFR00000000099"


@pytest.fixture
def log_path(tmp_path: Path) -> Iterator[Path]:
    yield setup_logging(tmp_path / "logs")
    stop_logging()


def test_report_masks_identifiers_and_home(
    log_path: Path, fake_enumeration: list[dict[str, Any]]
) -> None:
    fake_enumeration.append(hid_entry(serial_number=SERIAL, manufacturer_string=MANUFACTURER))
    logging.getLogger("rimlight.x").warning("opened %s", Path.home() / "secret")
    report = collect_report(log_path)
    assert "37fa:8202" in report
    assert SERIAL not in report
    assert MANUFACTURER not in report
    assert mask_identifier(SERIAL) in report
    assert str(Path.home()) not in report
    assert "opened ~" in report


def test_report_prints_each_device_field_on_its_own_line(
    tmp_path: Path, fake_enumeration: list[dict[str, Any]]
) -> None:
    fake_enumeration.append(hid_entry())
    lines = collect_report(tmp_path / "missing.log").splitlines()
    assert '  "driver": "37fa:8202",' in lines
    assert '  "usage_page": 65280,' in lines


def test_report_without_device_or_log(
    tmp_path: Path, fake_enumeration: list[dict[str, Any]]
) -> None:
    report = collect_report(tmp_path / "missing.log")
    assert "no supported devices found" in report
    assert "(no log file)" in report


def test_report_survives_enumeration_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(vendor_id: int = 0, product_id: int = 0) -> list[dict[str, Any]]:
        raise OSError("hid is broken")

    monkeypatch.setattr("hid.enumerate", fail)
    assert "listing devices failed: hid is broken" in collect_report(tmp_path / "missing.log")


def test_cli_prints_the_report(
    fake_enumeration: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["diagnostics"]) == 0
    assert "no supported devices found" in capsys.readouterr().out
