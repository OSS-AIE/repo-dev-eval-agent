from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RepoPolicy:
    name: str
    labels_any: List[str]
    branch_prefix: str
    commit_template: str
    pr_title_template: Dict[str, str]
    checks: List[str]
    fix_command: str


@dataclass
class AppConfig:
    daily_target_prs: int
    default_max_issue_scan: int
    workspace_root: str
    repos: List[RepoPolicy]


@dataclass
class Issue:
    number: int
    title: str
    body: str
    html_url: str
    labels: List[str]
    is_pull_request: bool

    @property
    def issue_type(self) -> str:
        lowered = " ".join(self.labels).lower() + " " + self.title.lower()
        if "feature" in lowered or "enhancement" in lowered:
            return "feature"
        return "bug"
