import base64
import re
import subprocess
import sys
from collections.abc import Sequence

import pytest

from rimlight.device.driver import DeviceMatch
from rimlight.device.drivers.strip_37fa_8202 import Strip37FA8202Driver
from rimlight.device.reset import (
    ScheduledTaskResetter,
    create_resetter,
    elevated_command,
    install_script,
    restart_command,
    task_name,
    uninstall_script,
)
from rimlight.device.usb_nodes import UsbId

MATCH = DeviceMatch(0x37FA, 0x8202)
TASK = "rimlight-restart-37fa-8202"
BOOTLOADER = UsbId(0x4348, 0x55E0)


class FakeRunner:
    def __init__(self, code: int = 0) -> None:
        self.code = code
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str], timeout: float) -> int:
        self.commands.append(list(command))
        return self.code


def _decoded_script(command: Sequence[str]) -> str:
    match = re.search(r"-EncodedCommand (\S+?)'", command[-1])
    assert match is not None
    return base64.b64decode(match[1]).decode("utf-16-le")


def test_task_name_comes_from_the_device() -> None:
    assert task_name(MATCH) == TASK


def _node_pattern(command: str) -> str:
    match = re.search(r"-Match '(.+?)'", command)
    assert match is not None
    return match[1]


def test_restart_command_targets_only_the_devices_usb_node() -> None:
    command = restart_command(MATCH)
    pattern = _node_pattern(command)
    assert re.search(pattern, "USB\\VID_37FA&PID_8202\\ANY")
    assert not re.search(pattern, "USB\\VID_4348&PID_55E0\\ANY")
    assert "pnputil /restart-device" in command
    assert '"' not in command  # it goes inside a double-quoted command line


def test_restart_command_also_targets_the_bootloader_node() -> None:
    command = restart_command(MATCH, BOOTLOADER)
    pattern = _node_pattern(command)
    assert re.search(pattern, "USB\\VID_37FA&PID_8202\\ANY")
    assert re.search(pattern, "USB\\VID_4348&PID_55E0\\ANY")
    assert not re.search(pattern, "USB\\VID_046D&PID_C53F\\ANY")
    assert not re.search(pattern, "HID\\VID_4348&PID_55E0\\ANY")
    assert '"' not in command


def test_task_restarts_the_bootloader_node_the_driver_declares() -> None:
    assert Strip37FA8202Driver.bootloader == BOOTLOADER
    resetter = create_resetter(Strip37FA8202Driver)
    if sys.platform == "win32":
        assert isinstance(resetter, ScheduledTaskResetter)
        run = FakeRunner()
        ScheduledTaskResetter(MATCH, bootloader=BOOTLOADER, run=run).install()
        assert _decoded_script(run.commands[0]) == install_script(MATCH, BOOTLOADER)


def test_task_runs_only_a_system_binary_as_system() -> None:
    script = install_script(MATCH)
    assert 'Join-Path $env:SystemRoot "System32' in script
    assert '-UserId "SYSTEM"' in script
    assert f'-TaskName "{TASK}"' in script
    assert restart_command(MATCH).replace("'", "''") in script


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "win32", reason="needs PowerShell")
@pytest.mark.parametrize(
    "script",
    [install_script(MATCH), install_script(MATCH, BOOTLOADER), uninstall_script(MATCH)],
)
def test_scripts_are_valid_powershell(script: str) -> None:
    """Parsed only, never run."""
    check = (
        "$errors = $null; "
        "[void][System.Management.Automation.Language.Parser]::ParseInput("
        "[Console]::In.ReadToEnd(), [ref]$null, [ref]$errors); "
        "$errors | ForEach-Object { $_.Message }; exit $errors.Count"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", check],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout


def test_users_may_only_read_and_start_the_task() -> None:
    assert "(A;;GRGX;;;AU)" in install_script(MATCH)


def test_elevated_command_asks_for_uac_and_passes_the_failure_on() -> None:
    command = elevated_command("script")
    assert "-Verb RunAs" in command[-1]
    assert "exit $p.ExitCode" in command[-1]
    assert _decoded_script(command) == "script"


def test_reset_starts_the_task() -> None:
    run = FakeRunner()
    ScheduledTaskResetter(MATCH, run=run).reset()
    assert run.commands == [["schtasks", "/run", "/tn", TASK]]


def test_reset_failure_is_an_oserror() -> None:
    with pytest.raises(OSError, match="exit code 5"):
        ScheduledTaskResetter(MATCH, run=FakeRunner(5)).reset()


@pytest.mark.parametrize(("code", "installed"), [(0, True), (1, False)])
def test_is_installed(code: int, installed: bool) -> None:
    run = FakeRunner(code)
    assert ScheduledTaskResetter(MATCH, run=run).is_installed() is installed
    assert run.commands == [["schtasks", "/query", "/tn", TASK]]


def test_install_and_uninstall_run_elevated() -> None:
    run = FakeRunner()
    resetter = ScheduledTaskResetter(MATCH, run=run)
    resetter.install()
    resetter.uninstall()
    assert _decoded_script(run.commands[0]) == install_script(MATCH)
    assert _decoded_script(run.commands[1]) == uninstall_script(MATCH)


def test_refused_uac_prompt_is_an_oserror() -> None:
    with pytest.raises(OSError, match="could not install"):
        ScheduledTaskResetter(MATCH, run=FakeRunner(1)).install()


def test_resetter_exists_only_on_windows() -> None:
    resetter = create_resetter(Strip37FA8202Driver)
    assert (resetter is not None) == (sys.platform == "win32")
