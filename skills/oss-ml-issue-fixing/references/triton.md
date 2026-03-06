# triton-lang/triton

## Architecture Snapshot (from local mirror)

- Compiler and IR code:
- `include/triton/` and `lib/` (dialects, analyses, passes, lowering)
- Python frontend/runtime:
- `python/triton/`
- Tests:
- `python/test/` (pytest) and `test/` (lit)
- Build/config:
- `cmake/`, `CMakeLists.txt`, `pyproject.toml`

## Contributing / Dev Rules (from local docs)

- Contributor governance and decision process documented in `CONTRIBUTING.md`.
- README emphasizes:
- `pip install -r python/requirements.txt`
- `pip install -e .`
- Common tests:
- `make test`
- `make test-nogpu`
- AGENTS hints:
- Rebuild before tests (`make`)
- Prefer targeted pytest and lit runs for compiler changes.

## Agent Tips

- Python runtime issues: inspect `python/triton/` + `python/test/unit`.
- Compiler backend issues: inspect `lib/`, `include/`, and matching lit tests in `test/`.
- For reproducible compiler failures, prefer lit-based minimal reproducer additions.
