# Repo Dev Eval Agent

Evaluate open-source repositories for developer experience, local build/test
readiness, Markdown quality, and PR pipeline efficiency.

## What Is Implemented

- Full-repository Markdown scanning, not only `README.md`
- Community doc skill registry for repos whose README points to external setup guides
- Local build / unit-test / code-check command inference and execution
- Docker / devcontainer / workflow container readiness detection
- GitHub Actions PR duration and runner resource estimation
- GitCode / GitHub AI review signal detection
- Configurable AI CLI adapter support for `codex`, `opencode`, and custom tools
- One-shot CLI report generation for repository lists

The original OSS issue-fixing automation is still present in this codebase and
can be used separately.

## Quick Start

```powershell
cd D:\vbox\repos\repo_dev_eval_agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

## Repo Evaluation Agent

Architecture:

- [specs/repo-eval-agent-architecture.md](specs/repo-eval-agent-architecture.md)

Sample config:

- [config/repo_eval.sample.yaml](config/repo_eval.sample.yaml)

Config-driven evaluation:

```powershell
$env:PYTHONPATH='src'
python -m oss_issue_fixer.cli evaluate-repos `
  --config config/repo_eval.sample.yaml `
  --repo vllm-project/vllm `
  --no-ai `
  --report-md reports/eval/sample.md `
  --report-json reports/eval/sample.json
```

One-shot evaluation without writing a config file:

```powershell
$env:PYTHONPATH='src'
python -m oss_issue_fixer.cli assess-repos `
  --repo https://github.com/vllm-project/vllm `
  --repo https://gitcode.com/Ascend/MindIE-SD `
  --pr-window-days 30 `
  --local-runner wsl `
  --wsl-distro Ubuntu `
  --enable-local-commands `
  --report-root reports/eval
```

This one-shot command will:

- resolve repo URLs / local paths automatically
- scan all Markdown files instead of only `README.md`
- optionally merge Markdown from remote refs such as `origin/main` / `origin/master`
- infer local build / unit-test / code-check commands
- optionally run commands through WSL for Linux-oriented repos
- compute GitHub PR workflow average duration within a configurable time window
- detect AI code-review signals from GitHub reviews/comments or GitCode PR comments
- generate Markdown, HTML, and JSON reports in one run

Batch evaluation from Excel:

```powershell
$env:PYTHONPATH='src'
python -m oss_issue_fixer.cli assess-repos `
  --repo-xlsx "C:\Users\Administrator\Downloads\openlibing代码仓数据.xlsx" `
  --report-root reports/eval `
  --report-prefix openlibing
```

Excel input expectations:

- the first sheet is used by default
- or pass `--repo-sheet <sheet-name>`
- use `--repo-offset` / `--repo-limit` to run the workbook in chunks
- supported URL column headers:
  - `仓库链接`
  - `repo_url`
  - `repository_url`
  - `url`

Tracked sample input:

- `input/openlibing-code-repos.xlsx`

Community doc skills:

- `skills/community_docs/registry.yaml`
- Use this registry when a repository points to external docs sites or GitHub / GitCode blob pages for local build, test, code-check, or container instructions.

HTML report behavior:

- top-level summary table across all repositories
- one tab per repository for detailed findings
- suitable for sharing as a single-file report artifact

Tracked sample reports:

- `reports/samples/sample-vllm.md`
- `reports/samples/sample-vllm.html`
- `reports/samples/real-focus.md`
- `reports/samples/real-focus.html`
- `reports/samples/openlibing-smoke.md`
- `reports/samples/openlibing-smoke.html`

Optional AI summary adapter:

- the adapter is configurable and not hard-coded to Codex
- current built-in default templates:
  - `codex` / `openai-codex`
  - `opencode`
- tools such as `claudecode`, `trae`, or other CLIs can be used by passing:
  - `--enable-ai`
  - `--ai-provider <name>`
  - `--ai-command <path>`
  - `--ai-command-template '<template>'`

Example using Codex first for debugging:

```powershell
$env:PYTHONPATH='src'
python -m oss_issue_fixer.cli assess-repos `
  --repo https://github.com/vllm-project/vllm `
  --enable-ai `
  --ai-provider codex `
  --ai-command codex.cmd `
  --report-root reports/eval
```

If you want the agent to execute local build/test commands, either:

- set `enable_local_commands: true` in config, or
- pass `--enable-local-commands`

Remote platform credentials:

- `GITHUB_TOKEN`: enables GitHub Actions / PR review metric collection
- `GITCODE_TOKEN`: enables GitCode PR comment inspection, including robot review detection such as `ascend-robot`

Set environment variables:

- `GITHUB_TOKEN`
- `GITCODE_TOKEN`
- `OPENAI_MODEL` (optional)
- `CODEX_FIXER_TIMEOUT_SEC` (optional, default `1800`)

## Issue Fixer Automation

The original issue-fixing flow is still available:

```powershell
python -m oss_issue_fixer.cli run-once --config config/repos.yaml --max-prs 2
```

Local smoke test:

```powershell
$env:ALLOW_STUB_FALLBACK='1'
python -m oss_issue_fixer.cli run-local-smoke --config config/repos.yaml --repo vllm-project/vllm --skip-checks
```

## Notes

- GitHub PR metrics are more stable with an authenticated `GITHUB_TOKEN`
- GitCode PR bot-comment collection requires `GITCODE_TOKEN`
- Linux-first repositories usually work better with `--local-runner wsl`

## GitHub Actions Baseline

This repository now includes:

- `.github/workflows/ci.yml`
  - build package artifacts
  - run `pytest`
  - run `pre-commit`
  - run `actionlint`
- `.github/workflows/codeql.yml`
  - run official GitHub CodeQL analysis for Python
  - trigger on `pull_request`, `push main`, weekly schedule, and manual dispatch
  - upload security results to GitHub code scanning
- `.github/workflows/codex-pr-review.yml`
  - Codex / OpenAI-based PR review comment
  - safe by default: uses `pull_request_target` but only reads PR metadata/diff through GitHub API
  - requires `OPENAI_API_KEY`
- `.github/workflows/gemini-pr-review.yml`
  - Gemini-based PR review comment
  - same safe execution model as Codex review
  - requires `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- `.gemini/config.yaml` + `.gemini/styleguide.md`
  - native Gemini Code Assist repository customization
  - does not require this repository to call Gemini APIs from Actions
  - intended for the GitHub-side Gemini Code Assist integration, similar to `vllm-project/vllm-ascend`

Recommended repository configuration:

- Actions secret: `OPENAI_API_KEY`
- Optional Actions secret: `OPENAI_BASE_URL`
- Optional Actions variable: `OPENAI_REVIEW_MODEL`
- Actions secret: `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- Optional Actions secret: `GEMINI_BASE_URL`
- Optional Actions variable: `GEMINI_REVIEW_MODEL`
- Install / enable Gemini Code Assist for GitHub if you want native Gemini PR summaries/comments driven by `.gemini/*`

Behavior notes:

- Codex and Gemini each publish their own sticky PR comment and update it on re-run
- comment markers are separated, so two providers can run in parallel without overwriting each other
- native Gemini repository behavior can also be customized without Secrets by `.gemini/config.yaml`
- default models:
  - OpenAI: `gpt-5-mini`
  - Gemini: `gemini-2.5-flash`
