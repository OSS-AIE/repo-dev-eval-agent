from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import AppConfig, RepoPolicy
from .quality import run_quality_gates


@dataclass
class SmokeResult:
    repo: str
    issue_number: int
    changed: bool
    checks_passed: bool
    branch: str
    worktree: str


def _run(cmd: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )


def _find_repo(cfg: AppConfig, repo_name: str) -> RepoPolicy:
    for repo in cfg.repos:
        if repo.name == repo_name:
            return repo
    raise RuntimeError(f"Repo not found in config: {repo_name}")


def run_local_smoke(
    cfg: AppConfig,
    repo_name: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    skip_checks: bool = True,
) -> SmokeResult:
    repo = _find_repo(cfg, repo_name)
    local_dir = Path(cfg.workspace_root).resolve() / repo_name.replace("/", "__")
    if not local_dir.exists():
        raise RuntimeError(f"Local mirror not found: {local_dir}")

    current = _run("git rev-parse --abbrev-ref HEAD", local_dir)
    if current.returncode != 0:
        raise RuntimeError(current.stderr.strip())
    base_branch = current.stdout.strip()
    branch = f"{repo.branch_prefix}/smoke-{issue_number}"
    for cmd in (f"git checkout {base_branch}", f"git checkout -B {branch}"):
        r = _run(cmd, local_dir)
        if r.returncode != 0:
            raise RuntimeError(f"{cmd}: {r.stderr.strip()}")

    context_path = local_dir / ".ai-agent-context.json"
    context_path.write_text(
        json.dumps(
            {
                "repo": repo.name,
                "issue": {
                    "number": issue_number,
                    "title": issue_title,
                    "body": issue_body,
                    "labels": ["bug", "smoke-test"],
                    "url": f"https://github.com/{repo.name}/issues/{issue_number}",
                    "type": "bug",
                },
                "contributing_excerpt": "",
                "generated_at": datetime.utcnow().isoformat() + "Z",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    cmd = repo.fix_command.format(
        issue_number=issue_number,
        repo=repo.name,
        issue_type="bug",
        title=issue_title.replace('"', "'"),
        context_path=str(context_path.name),
    )
    fixed = subprocess.run(
        cmd,
        cwd=str(local_dir),
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=max(60, repo.fix_timeout_sec),
        env={
            **dict(os.environ),
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        },
    )
    if fixed.returncode != 0:
        raise RuntimeError(f"fix command failed: {fixed.stderr.strip()}")

    changed = _run("git status --porcelain", local_dir).stdout.strip() != ""
    checks_passed = True
    if not skip_checks and changed:
        checks_passed, _ = run_quality_gates(local_dir, repo.checks)

    return SmokeResult(
        repo=repo.name,
        issue_number=issue_number,
        changed=changed,
        checks_passed=checks_passed,
        branch=branch,
        worktree=str(local_dir),
    )
