# OSS Issue Fixer Agent

Automate issue triage, patch generation, checks, and PR submission for major OSS ML repos.

## Target Repositories

- `pytorch/pytorch`
- `vllm-project/vllm`
- `sgl-project/sglang`
- `triton-lang/triton`

Configured in [config/repos.yaml](config/repos.yaml).

## What Is Implemented

- Scan open issues by labels.
- Fork/clone target repos and create issue branches.
- Build issue context with CONTRIBUTING excerpt.
- Run `codex exec` non-interactively to generate code fixes.
- Run quality gates before commit/PR.
- Push branch and create PR automatically.
- Persist issue states in `.work/.agent-state.json`:
- already submitted issues will not be retried
- failed issues are retried only after cooldown

## Quick Start

```powershell
cd D:\vbox\repos\oss-issue-fixer-agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

Set environment variables (system/user scope recommended):

- `GITHUB_TOKEN` (required)
- `OPENAI_MODEL` (optional)
- `CODEX_FIXER_TIMEOUT_SEC` (optional, default `1800`)

Codex CLI requirement:

```powershell
codex.cmd login
codex.cmd exec --help
```

## Run Once

```powershell
python -m oss_issue_fixer.cli run-once --config config/repos.yaml --max-prs 2
```

Run for a single repository:

```powershell
python -m oss_issue_fixer.cli run-once --config config/repos.yaml --repo vllm-project/vllm --max-prs 1 --dry-run
```

Write machine-readable result:

```powershell
python -m oss_issue_fixer.cli run-once --config config/repos.yaml --result-json reports/run-once.json
```

## Local Smoke Test (No GitHub/OpenAI Network)

When network is blocked, validate local pipeline with fallback stub:

```powershell
$env:ALLOW_STUB_FALLBACK='1'
python -m oss_issue_fixer.cli run-local-smoke --config config/repos.yaml --repo vllm-project/vllm --skip-checks
```

This command validates:
- context generation
- fixer plugin invocation
- git change detection
- branch workflow

## Daily Automation (Local Windows)

Register scheduled task:

```powershell
.\tools\register_daily_task.ps1 -TaskName OSSIssueFixerDaily -Time 09:00
```

Manual run:

```powershell
.\tools\run_agent_daily.ps1 -MaxPrs 2
```

Logs are written to `logs/daily-run-*.log`.

Detailed plan: [specs/daily-automation-plan.md](specs/daily-automation-plan.md).

## Skills and Specs

- Skill package: [skills/oss-ml-issue-fixing/SKILL.md](skills/oss-ml-issue-fixing/SKILL.md)
- Repo references:
- [skills/oss-ml-issue-fixing/references/pytorch.md](skills/oss-ml-issue-fixing/references/pytorch.md)
- [skills/oss-ml-issue-fixing/references/vllm.md](skills/oss-ml-issue-fixing/references/vllm.md)
- [skills/oss-ml-issue-fixing/references/sglang.md](skills/oss-ml-issue-fixing/references/sglang.md)
- [skills/oss-ml-issue-fixing/references/triton.md](skills/oss-ml-issue-fixing/references/triton.md)
- Auto-generated local repo specs: `specs/repos/*.md` via:

```powershell
$env:PYTHONPATH='src'
python tools/generate_repo_specs.py --config config/repos.yaml --out-dir specs/repos
```

## Notes

- This environment may not have outbound network access; first-run clone/fork needs GitHub connectivity.
- Start with low `--max-prs` and tune checks in `config/repos.yaml` to match your compute budget.
- If Codex/OpenAI is unavailable, set `ALLOW_STUB_FALLBACK=1` for local smoke validation only.
