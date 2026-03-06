param(
  [string]$TaskName = "OSSIssueFixerDaily",
  [string]$Time = "09:00"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $repoRoot "tools\run_agent_daily.ps1"
if (-not (Test-Path $scriptPath)) {
  throw "Script not found: $scriptPath"
}

$taskAction = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

$taskTrigger = New-ScheduledTaskTrigger -Daily -At $Time
$taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $taskAction `
  -Trigger $taskTrigger `
  -Settings $taskSettings `
  -Description "Run OSS Issue Fixer Agent daily." `
  -Force | Out-Null

Write-Host "Task registered: $TaskName at $Time"
