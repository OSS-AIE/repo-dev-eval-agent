param(
  [string]$Branch = "feat/agent-hardening-20260306",
  [string]$Remote = "origin",
  [string]$CommitMessage = "feat: harden oss issue fixer and add local smoke workflow"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

git checkout -B $Branch
git add -A
git commit -m $CommitMessage
git push $Remote $Branch

Write-Host "Pushed branch: $Branch"
Write-Host "Open PR in your GitHub repo after push."
