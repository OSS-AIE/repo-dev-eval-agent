from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable


def run_quality_gates(worktree: Path, commands: Iterable[str]) -> tuple[bool, list[str]]:
    logs: list[str] = []
    for cmd in commands:
        completed = subprocess.run(
            cmd,
            cwd=str(worktree),
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
        logs.append(f"$ {cmd}\n{completed.stdout}\n{completed.stderr}")
        if completed.returncode != 0:
            return False, logs
    return True, logs
