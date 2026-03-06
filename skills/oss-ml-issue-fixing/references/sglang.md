# sgl-project/sglang

## Local Mirror Status

- Current workspace snapshot does not include `.work/sgl-project__sglang`.
- Let agent clone once, then regenerate spec:

```bash
python tools/generate_repo_specs.py --config config/repos.yaml --out-dir specs/repos
```

## Baseline Architecture Guide (to verify after clone)

- Typical core areas:
- `python/sglang` or `sglang/` serving/runtime logic
- scheduler/executor/runtime modules for serving paths
- `test/` or `tests/` coverage for runtime and API behavior

## Expected Contribution Focus

- Keep fixes scoped to one serving/runtime subsystem.
- Add minimal reproducible tests where possible.
- After first clone, treat `specs/repos/sgl-project__sglang.md` as source of truth for this workspace.
