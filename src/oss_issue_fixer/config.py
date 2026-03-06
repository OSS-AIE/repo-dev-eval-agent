from __future__ import annotations

from pathlib import Path

import yaml

from .models import AppConfig, RepoPolicy


def load_config(path: str) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    repos = [
        RepoPolicy(
            name=item["name"],
            labels_any=item.get("labels_any", []),
            branch_prefix=item.get("branch_prefix", "ai-fix"),
            commit_template=item["commit_template"],
            pr_title_template=item["pr_title_template"],
            checks=item.get("checks", []),
            fix_command=item["fix_command"],
            fix_timeout_sec=int(item.get("fix_timeout_sec", 1800)),
        )
        for item in raw["repos"]
    ]
    return AppConfig(
        daily_target_prs=int(raw.get("daily_target_prs", 10)),
        default_max_issue_scan=int(raw.get("default_max_issue_scan", 30)),
        attempt_cooldown_hours=int(raw.get("attempt_cooldown_hours", 24)),
        workspace_root=raw.get("workspace_root", ".work"),
        repos=repos,
    )
