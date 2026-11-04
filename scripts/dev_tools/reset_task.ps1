# Experiment for issue #21: can a non-administrator restart the strip through a scheduled task?
#
# Run from an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\dev_tools\reset_task.ps1 install
#   powershell -ExecutionPolicy Bypass -File scripts\dev_tools\reset_task.ps1 uninstall
#
# The task runs as SYSTEM and only ever executes the fixed system command below, never a file a
# normal user could replace. Authenticated users may start it but not change it.

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("install", "uninstall")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$TaskName = "rimlight-restart-strip"

if ($Action -eq "uninstall") {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "Removed task $TaskName."
    exit 0
}

$Command = "Get-PnpDevice | Where-Object InstanceId -Match '^USB\\VID_37FA&PID_8202\\' | " +
    "ForEach-Object { pnputil /restart-device `$_.InstanceId }"
$TaskAction = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -Command `"$Command`""
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName -Action $TaskAction -Principal $Principal `
    -Settings $Settings -Force | Out-Null

# Let authenticated users read and start the task. Without this only administrators can.
$Service = New-Object -ComObject "Schedule.Service"
$Service.Connect()
$Task = $Service.GetFolder("\").GetTask($TaskName)
$Descriptor = $Task.GetSecurityDescriptor(0xF)
$Task.SetSecurityDescriptor($Descriptor + "(A;;GRGX;;;AU)", 0)

Write-Output "Installed task $TaskName. Test it from a normal (not elevated) terminal."
