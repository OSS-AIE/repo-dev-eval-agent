# Optimization Archive (2026-03-06)

## Scope

- Improve reliability for daily autonomous runs.
- Add local verifiable test path for restricted-network environments.
- Preserve online flow for real issue fixing and PR submission.

## Changes

- Added real fixer plugin:
- `src/oss_issue_fixer/plugins/codex_fixer.py`
- Tries `codex exec` first.
- Supports `ALLOW_STUB_FALLBACK=1` for offline smoke mode.

- Added state management:
- `src/oss_issue_fixer/state.py`
- Avoids retrying already submitted issues.
- Applies cooldown to failed issues.

- Enhanced agent run controls:
- Repo filtering (`--repo` in `run-once`).
- Fix timeout per repo (`fix_timeout_sec`).
- Fixer logs persisted in `.ai-agent/fixer-<issue>.log`.
- Result export (`--result-json`).

- Added local smoke command:
- `run-local-smoke` in CLI.
- `src/oss_issue_fixer/smoke.py`
- Enables local end-to-end validation using local repo mirror.

- Added repo spec generation:
- `tools/generate_repo_specs.py`
- Produces `specs/repos/*.md` and `*.json` for architecture/contributing snapshots.

- Added Windows daily automation scripts:
- `tools/run_agent_daily.ps1`
- `tools/register_daily_task.ps1`

- Improved API error visibility:
- Wrapped GitHub request failures with clearer messages.

## Verified in Current Environment

- Local smoke completed for `vllm-project/vllm`:
- Branch: `ai-fix/smoke-81234`
- Change created: `.ai-agent/issue-81234.md`
- Because outbound network is blocked, Codex and GitHub calls fail; fallback mode used for local validation.

## Pending for Real PR Submission

- Restore outbound access to:
- `https://api.github.com`
- `https://api.openai.com`
- Set valid `GITHUB_TOKEN` with fork/pull request permissions.
- Run:
- `python -m oss_issue_fixer.cli run-once --config config/repos.yaml --repo vllm-project/vllm --max-prs 1`
