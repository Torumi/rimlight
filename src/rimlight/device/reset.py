"""Restarting a hung device from a normal user account.

On Windows, restarting a device needs administrator rights, so one elevated setup registers a
scheduled task that a normal user may start. The task runs as SYSTEM and only ever executes system
binaries with a fixed command, never a file a normal user could replace.
"""

import base64
import logging
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Final

from rimlight.device.driver import DeviceMatch

_log = logging.getLogger(__name__)

_RUN_TIMEOUT_S: Final = 30.0
_ELEVATED_TIMEOUT_S: Final = 300.0  # includes the user answering the UAC prompt

type CommandRunner = Callable[[Sequence[str], float], int]
"""Runs a command and returns its exit code. Raises OSError if it cannot run."""


def _run_hidden(command: Sequence[str], timeout: float) -> int:
    """Run without a console window flashing up, as the app has no console of its own."""
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=timeout, check=False, creationflags=no_window
        )
    except subprocess.SubprocessError as exc:
        raise OSError(f"{command[0]} failed: {exc}") from exc
    return result.returncode


def task_name(match: DeviceMatch) -> str:
    return f"rimlight-restart-{match.vendor_id:04x}-{match.product_id:04x}"


def restart_command(match: DeviceMatch) -> str:
    """PowerShell restarting the device's USB node. The IDs are integers, so nothing is injected."""
    node = f"^USB\\\\VID_{match.vendor_id:04X}&PID_{match.product_id:04X}\\\\"
    return (
        f"Get-PnpDevice | Where-Object InstanceId -Match '{node}' | "
        "ForEach-Object { pnputil /restart-device $_.InstanceId }"
    )


def install_script(match: DeviceMatch) -> str:
    """PowerShell, run elevated, registering the task and letting users start it."""
    name = task_name(match)
    # The task's command line is quoted with double quotes; it contains none itself. It sits in
    # a single-quoted PowerShell string here, where a single quote is written twice.
    command = restart_command(match).replace("'", "''")
    return f"""$ErrorActionPreference = "Stop"
$Shell = Join-Path $env:SystemRoot "System32\\WindowsPowerShell\\v1.0\\powershell.exe"
$Arguments = '-NoProfile -NonInteractive -Command "{command}"'
$Action = New-ScheduledTaskAction -Execute $Shell -Argument $Arguments
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "{name}" -Action $Action -Principal $Principal `
    -Settings $Settings -Force | Out-Null
$Service = New-Object -ComObject "Schedule.Service"
$Service.Connect()
$Task = $Service.GetFolder("\\").GetTask("{name}")
$Task.SetSecurityDescriptor($Task.GetSecurityDescriptor(0xF) + "(A;;GRGX;;;AU)", 0)
"""


def uninstall_script(match: DeviceMatch) -> str:
    return (
        '$ErrorActionPreference = "Stop"\n'
        f'Unregister-ScheduledTask -TaskName "{task_name(match)}" -Confirm:$false\n'
    )


def elevated_command(script: str) -> list[str]:
    """A command showing the UAC prompt and running `script` elevated; fails if it is refused."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    shell = "powershell.exe"
    launcher = (
        f"$p = Start-Process {shell} -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
        f"-ArgumentList '-NoProfile -NonInteractive -EncodedCommand {encoded}'; "
        "exit $p.ExitCode"
    )
    return [shell, "-NoProfile", "-NonInteractive", "-Command", launcher]


class ScheduledTaskResetter:
    """Restarts the device through its scheduled task. Needs no elevation once installed."""

    def __init__(self, match: DeviceMatch, *, run: CommandRunner = _run_hidden) -> None:
        self._match = match
        self._name = task_name(match)
        self._run = run

    def is_installed(self) -> bool:
        return self._run(["schtasks", "/query", "/tn", self._name], _RUN_TIMEOUT_S) == 0

    def reset(self) -> None:
        code = self._run(["schtasks", "/run", "/tn", self._name], _RUN_TIMEOUT_S)
        if code != 0:
            raise OSError(f"could not start the restart task (exit code {code})")
        _log.info("started the device restart task")

    def install(self) -> None:
        """Asks for elevation once. Raises OSError if refused or failed."""
        self._run_elevated(install_script(self._match), "install")

    def uninstall(self) -> None:
        """Asks for elevation once. Raises OSError if refused or failed."""
        self._run_elevated(uninstall_script(self._match), "remove")

    def _run_elevated(self, script: str, action: str) -> None:
        code = self._run(elevated_command(script), _ELEVATED_TIMEOUT_S)
        if code != 0:
            raise OSError(f"could not {action} the restart task (exit code {code})")


def create_resetter(match: DeviceMatch) -> ScheduledTaskResetter | None:
    """The platform's way to restart a device, or None where there is none yet."""
    if sys.platform == "win32":
        return ScheduledTaskResetter(match)
    return None
