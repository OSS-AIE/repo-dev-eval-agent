from __future__ import annotations

import argparse
import json
from pathlib import Path

from oss_issue_fixer.config import load_config


def read_first_existing(base: Path, candidates: list[str], max_chars: int = 12000) -> str:
    for rel in candidates:
        p = base / rel
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    return ""


def top_level_dirs(base: Path, limit: int = 30) -> list[str]:
    names = [p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")]
    names.sort()
    return names[:limit]


def build_spec(repo_dir: Path, repo_name: str) -> dict:
    readme = read_first_existing(repo_dir, ["README.md", "README.rst"])
    contributing = read_first_existing(
        repo_dir,
        ["CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"],
    )
    dev_docs = [
        p
        for p in (
            "docs",
            "DEVELOPMENT.md",
            "CONTRIBUTING.md",
            ".github/CONTRIBUTING.md",
            "AGENTS.md",
        )
        if (repo_dir / p).exists()
    ]
    return {
        "repo": repo_name,
        "local_path": str(repo_dir),
        "top_level_dirs": top_level_dirs(repo_dir),
        "dev_docs": dev_docs,
        "readme_excerpt": readme,
        "contributing_excerpt": contributing,
    }


def to_markdown(payload: dict) -> str:
    lines = [
        f"# {payload['repo']}",
        "",
        f"- Local path: `{payload['local_path']}`",
        f"- Top-level dirs: `{', '.join(payload['top_level_dirs'])}`",
        f"- Dev docs: `{', '.join(payload['dev_docs'])}`",
        "",
        "## README Excerpt",
        "",
        "```text",
        payload["readme_excerpt"][:8000],
        "```",
        "",
        "## CONTRIBUTING Excerpt",
        "",
        "```text",
        payload["contributing_excerpt"][:8000],
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/repos.yaml")
    parser.add_argument("--out-dir", default="specs/repos")
    args = parser.parse_args()

    cfg = load_config(args.config)
    workspace = Path(cfg.workspace_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    for repo in cfg.repos:
        local_dir = workspace / repo.name.replace("/", "__")
        slug = repo.name.replace("/", "__")
        if not local_dir.exists():
            missing = {
                "repo": repo.name,
                "local_path": str(local_dir),
                "status": "missing",
                "hint": "Repo mirror not found. Let the agent clone it, then rerun this script.",
            }
            (out_dir / f"{slug}.json").write_text(
                json.dumps(missing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (out_dir / f"{slug}.md").write_text(
                f"# {repo.name}\n\n- Local path: `{local_dir}`\n- Status: missing\n"
                "- Hint: let the agent clone this repo first, then rerun `tools/generate_repo_specs.py`.\n",
                encoding="utf-8",
            )
            continue

        payload = build_spec(local_dir, repo.name)
        (out_dir / f"{slug}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / f"{slug}.md").write_text(to_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
