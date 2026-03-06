---
name: oss-ml-issue-fixing
description: Resolve GitHub issues and prepare PRs for pytorch/pytorch, vllm-project/vllm, sgl-project/sglang, and triton-lang/triton. Use when triaging issues, mapping to code areas, selecting checks, writing commit/PR titles, and applying repository-specific contributing rules.
---

# OSS ML Issue Fixing

Follow this workflow for `pytorch`, `vllm`, `sglang`, and `triton`.

## 1) Select repo profile

- For `pytorch/pytorch`, read `references/pytorch.md`.
- For `vllm-project/vllm`, read `references/vllm.md`.
- For `sgl-project/sglang`, read `references/sglang.md`.
- For `triton-lang/triton`, read `references/triton.md`.

If local mirror is missing, run:

```bash
python tools/generate_repo_specs.py --config config/repos.yaml --out-dir specs/repos
```

Use generated `specs/repos/*.md` as the latest local source snapshot.

## 2) Scope the issue

- Parse issue labels and title first.
- Map the issue to one subsystem directory from the repo profile.
- Keep patch minimal and avoid unrelated refactors.

## 3) Apply contribution constraints

- Respect `CONTRIBUTING.md` rules before changing code.
- Use repo-specific PR title prefixes.
- Add regression tests when behavior changed or bug fixed.

## 4) Validate before PR

- Run configured checks from `config/repos.yaml`.
- Require non-empty `git diff`.
- Commit only after checks pass.

## 5) Prepare PR text

- Include issue link, root cause summary, fix summary, and test evidence.
- Mention any limitations or follow-up work explicitly.
