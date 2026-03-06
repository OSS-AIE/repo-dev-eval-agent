# vllm-project/vllm

## Architecture Snapshot (from local mirror)

- Main package: `vllm/`
- Core runtime paths:
- `vllm/v1/engine/` (engine orchestration)
- `vllm/v1/core/` (scheduler, KV cache management)
- `vllm/v1/worker/` (GPU/CPU worker implementations)
- `vllm/v1/attention/` (attention backends and ops)
- Native/codegen paths:
- `csrc/`
- `vllm/_custom_ops.py` and kernel-related code under `vllm/v1/.../ops`
- Tests:
- `tests/` with model, kernel, and integration coverage

## Contributing / Dev Rules (from local docs)

- Primary contributing doc: `docs/contributing/README.md`
- Environment guidance:
- Prefer Python 3.12 for CI parity.
- Python-only dev can use `VLLM_USE_PRECOMPILED=1 uv pip install -e .`
- Kernel/C++ dev requires torch + build dependencies + editable install.
- Quality requirements:
- Use `pre-commit`, `pytest`, and add tests for fixes.
- PR title prefixes expected: `[Bugfix]`, `[Kernel]`, `[Core]`, `[Doc]`, etc.
- DCO sign-off is required (`git commit -s`).

## Agent Tips

- Bugfix issues often map to `vllm/v1/core`, `vllm/v1/engine`, or backend-specific paths.
- Keep PR titles aligned with contributing prefixes.
- Prefer focused tests (`pytest tests/<target> -q --maxfail=1`) before broader suites.
