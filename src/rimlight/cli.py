"""Debug CLI (`rimlight-cli`)."""

import argparse
import json
import logging
import sys
import time
from collections.abc import Sequence

from rimlight import __version__
from rimlight.device.registry import SupportedDevice, default_registry
from rimlight.diagnostics import collect_report, device_entry


def _table_row(device: SupportedDevice) -> tuple[str, ...]:
    info = device.info
    return (
        device.driver.id,
        str(info.interface_number),
        f"0x{info.usage_page:04X}" if info.usage_page else "?",
        f"0x{info.usage:02X}",
        info.product_string or "?",
        info.release_str,
        info.path.decode(errors="replace"),
    )


def _format_table(devices: Sequence[SupportedDevice]) -> str:
    headers = ("driver", "interface", "usage page", "usage", "product", "release", "path")
    rows = [_table_row(d) for d in devices]
    widths = [max(len(row[i]) for row in (headers, *rows)) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)) for row in rows]
    header = "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
    return "\n".join([header, *lines])


def _cmd_list(args: argparse.Namespace) -> int:
    registry = default_registry()
    devices = registry.find_supported(any_interface=args.all)
    if args.json:
        payload = [device_entry(d, show_serial=args.show_serial) for d in devices]
        print(json.dumps(payload, indent=2))
    elif devices:
        print(_format_table(devices))
    if not devices:
        ids = ", ".join(d.id for d in registry.drivers)
        print(f"No supported devices found (drivers: {ids}).", file=sys.stderr)
        return 1
    return 0


def _cmd_diagnostics(_args: argparse.Namespace) -> int:
    print(collect_report())
    return 0


def _cmd_recovery(args: argparse.Namespace) -> int:
    from rimlight.config.settings import RecoverySettings, load, save
    from rimlight.device.reset import create_resetter

    # Loading settings pulls in pydantic, so only commands that need them import it.
    settings = load().settings
    resetter = create_resetter(default_registry().drivers[0].match)
    if resetter is None:
        print("Automatic device restart is not available on this system yet.", file=sys.stderr)
        return 0 if args.action == "status" else 1

    def set_auto_reset(enabled: bool) -> None:
        recovery = RecoverySettings(auto_reset=enabled)
        save(settings.model_copy(update={"recovery": recovery}))

    try:
        match args.action:
            case "enable":
                if not resetter.is_installed():
                    print(
                        "Windows will now ask for permission for PowerShell: it registers a task "
                        "that restarts the device. This is asked only once."
                    )
                    resetter.install()
                set_auto_reset(True)
                print("Automatic restart is on.")
            case "disable":
                set_auto_reset(False)
                print("Automatic restart is off. The task stays installed; `remove` removes it.")
            case "remove":
                if resetter.is_installed():
                    print("Windows will now ask for permission for PowerShell to remove the task.")
                    resetter.uninstall()
                set_auto_reset(False)
                print("Automatic restart is off and the task is removed.")
            case _:
                state = "on" if settings.recovery.auto_reset else "off"
                task = "installed" if resetter.is_installed() else "not installed"
                print(f"Automatic restart: {state}; restart task: {task}.")
    except OSError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    from pydantic import ValidationError

    from rimlight.config.settings import LightSettings, load, save

    changes: dict[str, object] = {}
    if args.color is not None:
        changes["color"] = args.color
    if args.brightness is not None:
        changes["brightness"] = args.brightness / 100
    if args.on is not None:
        changes["on"] = args.on
    if not changes:
        print("Nothing to set; see --help.", file=sys.stderr)
        return 1
    settings = load().settings
    try:
        # Through the serialized form, so the color is validated like one from the file.
        current = settings.light.model_dump(mode="json")
        light = LightSettings.model_validate(current | changes)
    except ValidationError as exc:
        print(f"Invalid value: {exc.errors()[0]['msg']}", file=sys.stderr)
        return 1
    save(settings.model_copy(update={"light": light}))
    print("Saved. A running `rimlight-cli run` picks this up when restarted.")
    return 0


def _cmd_run(_args: argparse.Namespace) -> int:
    from rimlight.config.settings import load
    from rimlight.device.manager import DeviceState
    from rimlight.headless import available_resetter, run_with_defaults
    from rimlight.logs import setup_logging, stop_logging

    setup_logging()
    result = load()
    for problem in result.problems:
        logging.getLogger(__name__).warning("settings: %s", problem)
        print(f"Settings: {problem}", file=sys.stderr)

    def on_state(state: DeviceState) -> None:
        hint = "  (device not found; still looking)" if state is DeviceState.SEARCHING else ""
        print(f"{time.strftime('%H:%M:%S')} {state.name}{hint}", flush=True)

    def wait() -> None:
        print("Running. Press Ctrl+C to stop.", flush=True)
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    registry = default_registry()
    resetter = available_resetter(registry, result.settings)
    if resetter is not None:
        print("Automatic restart of a hung device: on.")
    else:
        print("Automatic restart of a hung device: off (see `rimlight-cli recovery`).")
    try:
        run_with_defaults(
            result.settings, registry, resetter=resetter, wait=wait, on_state=on_state
        )
    finally:
        stop_logging()
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

    p_diagnostics = sub.add_parser(
        "diagnostics", help="print a report for bug reports (identifiers masked, read-only)"
    )
    p_diagnostics.set_defaults(func=_cmd_diagnostics)

    p_recovery = sub.add_parser("recovery", help="automatic restart of a hung device")
    p_recovery.add_argument(
        "action",
        choices=("status", "enable", "disable", "remove"),
        help="enable may ask for administrator rights once; disable keeps the task; "
        "remove deletes it",
    )
    p_recovery.set_defaults(func=_cmd_recovery)

    p_set = sub.add_parser("set", help="change the saved light settings")
    p_set.add_argument("--color", help='color like "#ff8800"')
    p_set.add_argument("--brightness", type=float, help="brightness in percent, 0-100")
    power = p_set.add_mutually_exclusive_group()
    power.add_argument("--on", action="store_true", default=None, help="turn the light on")
    power.add_argument("--off", dest="on", action="store_false", help="turn the light off")
    p_set.set_defaults(func=_cmd_set)

    p_run = sub.add_parser(
        "run", help="hold the saved light without a window, recovering the device as needed"
    )
    p_run.set_defaults(func=_cmd_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
