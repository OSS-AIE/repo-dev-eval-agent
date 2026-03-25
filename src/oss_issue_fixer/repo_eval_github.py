from __future__ import annotations

import os
from typing import Any

import requests


class RepoEvalGitHubClient:
    def __init__(
        self,
        token: str | None = None,
        token_env: str = "GITHUB_TOKEN",
    ):
        self.token = token or os.getenv(token_env, "").strip()
        self.base = "https://api.github.com"
        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "repo-dev-eval-agent",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers.update(headers)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self.session.get(f"{self.base}{path}", params=params or {}, timeout=60)
        if resp.status_code == 404:
            return None
        try:
            resp.raise_for_status()
        except requests.RequestException as exc:
            detail = f" | body: {resp.text[:300]}" if resp.text else ""
            raise RuntimeError(f"GitHub GET failed: {path}: {exc}{detail}") from exc
        return resp.json()

    def list_workflow_runs(
        self, repo: str, event: str, per_page: int
    ) -> list[dict[str, Any]]:
        data = self._get(
            f"/repos/{repo}/actions/runs",
            params={"event": event, "per_page": per_page},
        )
        if not isinstance(data, dict):
            return []
        return list(data.get("workflow_runs", []) or [])

    def list_workflow_jobs(
        self, repo: str, run_id: int, per_page: int = 100
    ) -> list[dict[str, Any]]:
        data = self._get(
            f"/repos/{repo}/actions/runs/{run_id}/jobs",
            params={"per_page": per_page},
        )
        if not isinstance(data, dict):
            return []
        return list(data.get("jobs", []) or [])

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

    def list_reviews(self, repo: str, pull_number: int) -> list[dict[str, Any]]:
        data = self._get(f"/repos/{repo}/pulls/{pull_number}/reviews")
        return list(data or []) if isinstance(data, list) else []

    def list_issue_comments(self, repo: str, pull_number: int) -> list[dict[str, Any]]:
        data = self._get(f"/repos/{repo}/issues/{pull_number}/comments")
        return list(data or []) if isinstance(data, list) else []
