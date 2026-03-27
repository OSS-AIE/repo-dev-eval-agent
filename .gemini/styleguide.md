# Gemini Code Review Style Guide

## Review Goals

- Focus on correctness, regressions, missing tests, CI workflow risk, and maintainability.
- Prefer actionable comments over broad style-only commentary.
- Skip comments that merely restate the diff without adding value.
- If no concrete issue is found, say that explicitly.

## Comment Style

- Use Simplified Chinese.
- Keep each finding concise and specific.
- When possible, include:
  - the concrete risk
  - why it matters
  - one practical fix direction

## PR Summary Format

When Gemini generates a PR summary, prefer this structure:

```markdown
### What this PR does / why we need it?

- Summarize the functional change and the motivation.
- Mention the bug / gap / maintenance issue being addressed.

Fixes #<issue-number-if-known>

### Does this PR introduce any user-facing change?

- State `Yes` or `No`.
- If yes, mention API / CLI / report / workflow changes briefly.

### How was this patch tested?

- List the exact commands that were run.
- Call out any skipped checks or environment limits.
```

## Severity Guidance

- `HIGH`: correctness, security, data loss, workflow breakage, major regression
- `MEDIUM`: incomplete tests, brittle behavior, maintainability risks likely to matter soon
- `LOW`: optional cleanup or clarity improvements
