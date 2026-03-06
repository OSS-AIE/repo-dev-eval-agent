# pytorch/pytorch

## Local Mirror Status

- Current workspace snapshot does not include `.work/pytorch__pytorch`.
- Let agent clone once, then regenerate spec:

```bash
python tools/generate_repo_specs.py --config config/repos.yaml --out-dir specs/repos
```

## Baseline Architecture Guide (to verify after clone)

- Typical core areas:
- `torch/` Python frontend APIs
- `aten/` tensor operators and kernels
- `c10/` core abstractions
- `test/` large Python test suite
- `docs/` and `.github/` contribution tooling

## Expected Contribution Focus

- Use small, targeted fixes with regression tests under relevant `test/` modules.
- Respect repository CI scope; avoid broad refactors in issue-driven PRs.
- After first clone, treat `specs/repos/pytorch__pytorch.md` as source of truth for this workspace.
