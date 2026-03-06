param(
  [string]$ConfigPath = "config/repos.yaml",
  [int]$MaxPrs = 10,
  [string]$LogDir = "logs"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $LogDir "daily-run-$timestamp.log"

$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  $pythonExe = "python"
}

$env:PYTHONUTF8 = "1"
"[$(Get-Date -Format o)] starting run: max_prs=$MaxPrs config=$ConfigPath" | Tee-Object -FilePath $logPath

& $pythonExe -m oss_issue_fixer.cli run-once --config $ConfigPath --max-prs $MaxPrs 2>&1 | Tee-Object -FilePath $logPath -Append
$exitCode = $LASTEXITCODE

"[$(Get-Date -Format o)] exit_code=$exitCode" | Tee-Object -FilePath $logPath -Append
exit $exitCode
