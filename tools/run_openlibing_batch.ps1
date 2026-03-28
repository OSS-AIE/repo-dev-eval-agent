param(
    [string]$Workbook = "input/openlibing-code-repos.xlsx",
    [string]$ReportRoot = "reports/eval/openlibing-batch",
    [int]$ChunkSize = 50,
    [int]$StartOffset = 0,
    [int]$TotalRepos = 1086,
    [string]$WslDistro = "Ubuntu",
    [string]$WslWorkspaceRoot = "~/.cache/repo-dev-eval/repos",
    [int]$TimeoutSec = 3600
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:PYTHONPATH = "src"
New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null

for ($offset = $StartOffset; $offset -lt $TotalRepos; $offset += $ChunkSize) {
    $end = [Math]::Min($offset + $ChunkSize - 1, $TotalRepos - 1)
    $prefix = "openlibing-{0:D4}-{1:D4}" -f $offset, $end
    Write-Host "==> evaluating repos $offset .. $end"
    python -m oss_issue_fixer.cli assess-repos `
        --repo-xlsx $Workbook `
        --repo-offset $offset `
        --repo-limit $ChunkSize `
        --workspace-root ".work/eval" `
        --report-root $ReportRoot `
        --report-prefix $prefix `
        --local-runner wsl `
        --wsl-distro $WslDistro `
        --wsl-workspace-root $WslWorkspaceRoot `
        --enable-local-commands `
        --default-timeout-sec $TimeoutSec `
        --github-token-env GITHUB_TOKEN `
        --gitcode-token-env GITCODE_TOKEN
    if ($LASTEXITCODE -ne 0) {
        throw "chunk $prefix failed with exit code $LASTEXITCODE"
    }
}
