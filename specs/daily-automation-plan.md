# Daily Automation Plan (Local Codex CLI)

## Objective

- Run the issue fixer once per day from local machine.
- Use existing Codex CLI login (GPT Plus connected).
- Keep logs and detect failures quickly.

## Runtime Flow

1. Windows Task Scheduler triggers `tools/run_agent_daily.ps1` every day.
2. Script executes `python -m oss_issue_fixer.cli run-once --config config/repos.yaml`.
3. Agent fetches issues, runs `codex_fixer`, executes quality gates, then commits/pushes/opens PR.
4. Logs are stored under `logs/daily-run-*.log`.

## Prerequisites

- Codex CLI installed and logged in (`codex login` already completed).
- `GITHUB_TOKEN` available in system environment variables (PAT with repo scopes).
- Python virtual env prepared at `.venv` or system `python` available.

## One-time Setup

```powershell
cd D:\vbox\repos\oss-issue-fixer-agent
.\tools\register_daily_task.ps1 -TaskName OSSIssueFixerDaily -Time 09:00
```

## Operations

- Run immediately once:

```powershell
.\tools\run_agent_daily.ps1 -MaxPrs 3
```

- Inspect task:

```powershell
Get-ScheduledTask -TaskName OSSIssueFixerDaily
```

- Inspect latest logs:

```powershell
Get-ChildItem .\logs\ | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

## Recommended Guardrails

- Start with `MaxPrs=1~2` for 2-3 days.
- Keep `attempt_cooldown_hours` enabled to avoid repeated failed attempts.
- Tune `checks` in `config/repos.yaml` to avoid over-expensive full-suite runs per issue.
