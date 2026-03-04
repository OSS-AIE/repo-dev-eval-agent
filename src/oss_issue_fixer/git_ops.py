from __future__ import annotations

import subprocess
from pathlib import Path


def run(cmd: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )


def ensure_repo(local_dir: Path, clone_url: str) -> None:
    if local_dir.exists():
        result = run("git fetch --all --prune", local_dir)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return
    local_dir.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        f'git clone "{clone_url}" "{local_dir}"',
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())


def checkout_branch(local_dir: Path, base_branch: str, new_branch: str) -> None:
    cmds = [
        f"git checkout {base_branch}",
        "git pull --ff-only",
        f"git checkout -B {new_branch}",
    ]
    for cmd in cmds:
        result = run(cmd, local_dir)
        if result.returncode != 0:
            raise RuntimeError(f"{cmd}: {result.stderr.strip()}")


def has_changes(local_dir: Path) -> bool:
    result = run("git status --porcelain", local_dir)
    return bool(result.stdout.strip())


def commit_all(local_dir: Path, message: str) -> None:
    for cmd in ['git add -A', f'git commit -m "{message}"']:
        result = run(cmd, local_dir)
        if result.returncode != 0:
            raise RuntimeError(f"{cmd}: {result.stderr.strip()}")


def push_branch(local_dir: Path, branch: str) -> None:
    result = run(f"git push origin {branch} --force-with-lease", local_dir)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
