"""Debug CLI (`rimlight-cli`)."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

from rimlight import __version__
from rimlight.device.discovery import HidDeviceInfo, find_devices
from rimlight.device.ids import PRODUCT_ID, USAGE_PAGE, VENDOR_ID


def _format_table(devices: Sequence[HidDeviceInfo]) -> str:
    headers = ("interface", "usage page", "usage", "product", "release", "path")
    rows = [
        (
            str(d.interface_number),
            f"0x{d.usage_page:04X}" if d.usage_page else "?",
            f"0x{d.usage:02X}",
            d.product_string or "?",
            d.release_str,
            d.path.decode(errors="replace"),
        )
        for d in devices
    ]
    widths = [max(len(row[i]) for row in (headers, *rows)) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)) for row in rows]
    header = "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
    return "\n".join([header, *lines])


def mask_identifier(value: str, visible: int = 2) -> str:
    """Hide all but the last `visible` characters, e.g. "SN0000000042" -> "**********42"."""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


def _json_entry(device: HidDeviceInfo, show_serial: bool) -> dict[str, object]:
    entry: dict[str, object] = {**asdict(device), "path": device.path.decode(errors="replace")}
    if not show_serial:
        # Output gets pasted into public issues. The strip reports a unit-specific value in
        # its manufacturer string as well as in the serial number, so both are masked.
        entry["serial_number"] = mask_identifier(device.serial_number)
        entry["manufacturer_string"] = mask_identifier(device.manufacturer_string)
    return entry


def _cmd_list(args: argparse.Namespace) -> int:
    devices = find_devices(usage_page=None if args.all else USAGE_PAGE)
    if args.json:
        payload = [_json_entry(d, args.show_serial) for d in devices]
        print(json.dumps(payload, indent=2))
    elif devices:
        print(_format_table(devices))
    if not devices:
        scope = "" if args.all else f", usage page 0x{USAGE_PAGE:04X}"
        print(
            f"No HID interfaces found for {VENDOR_ID:04X}:{PRODUCT_ID:04X}{scope}.",
            file=sys.stderr,
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rimlight-cli", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list matching HID interfaces (read-only)")
    p_list.add_argument(
        "--all", action="store_true", help="show every interface of the device, any usage page"
    )
    p_list.add_argument("--json", action="store_true", help="machine-readable output")
    p_list.add_argument(
        "--show-serial",
        action="store_true",
        help="print serial and manufacturer strings unmasked (not for public issues)",
    )
    p_list.set_defaults(func=_cmd_list)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
