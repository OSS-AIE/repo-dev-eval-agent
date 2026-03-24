from __future__ import annotations

import os
from typing import Any

import requests


class RepoEvalGitCodeClient:
    def __init__(
        self,
        token: str | None = None,
        token_env: str = "GITCODE_TOKEN",
    ):
        self.token = token or os.getenv(token_env, "").strip()
        self.base = "https://api.gitcode.com/api/v5"
        self.session = requests.Session()
        headers = {
            "Accept": "application/json",
            "User-Agent": "repo-dev-eval-agent",
        }
        if self.token:
            headers["private-token"] = self.token
        self.session.headers.update(headers)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self.session.get(f"{self.base}{path}", params=params or {}, timeout=60)
        if resp.status_code == 404:
            return None
        try:
            resp.raise_for_status()
        except requests.RequestException as exc:
            detail = f" | body: {resp.text[:300]}" if resp.text else ""
            raise RuntimeError(f"GitCode GET failed: {path}: {exc}{detail}") from exc
        return resp.json()

    def list_recent_pulls(self, repo: str, per_page: int) -> list[dict[str, Any]]:
        data = self._get(
            f"/repos/{repo}/pulls",
            params={
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": per_page,
            },
        )
        return list(data or []) if isinstance(data, list) else []

    def list_pull_comments(self, repo: str, pull_number: int) -> list[dict[str, Any]]:
        data = self._get(f"/repos/{repo}/pulls/{pull_number}/comments")
        return list(data or []) if isinstance(data, list) else []
