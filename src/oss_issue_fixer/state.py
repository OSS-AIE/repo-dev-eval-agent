from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IssueState:
    status: str
    attempted_at: str
    reason: str = ""


class AgentStateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"issues": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _key(self, repo: str, issue_number: int) -> str:
        return f"{repo}#{issue_number}"

    def should_attempt(self, repo: str, issue_number: int, cooldown_hours: int) -> bool:
        raw = self.data.get("issues", {}).get(self._key(repo, issue_number))
        if not raw:
            return True
        state = IssueState(
            status=raw.get("status", "failed"),
            attempted_at=raw.get("attempted_at", ""),
            reason=raw.get("reason", ""),
        )
        if state.status == "submitted":
            return False
        try:
            last = datetime.fromisoformat(state.attempted_at)
        except ValueError:
            return True
        return _utc_now() - last >= timedelta(hours=max(1, cooldown_hours))

    def mark_failed(self, repo: str, issue_number: int, reason: str = "") -> None:
        self._mark(repo, issue_number, "failed", reason=reason)

    def mark_submitted(self, repo: str, issue_number: int) -> None:
        self._mark(repo, issue_number, "submitted")

    def _mark(self, repo: str, issue_number: int, status: str, reason: str = "") -> None:
        issues = self.data.setdefault("issues", {})
        issues[self._key(repo, issue_number)] = {
            "status": status,
            "attempted_at": _utc_now().isoformat(),
            "reason": reason[:500],
        }
        self._save()
