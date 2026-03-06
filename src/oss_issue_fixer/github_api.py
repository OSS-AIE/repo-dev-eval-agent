from __future__ import annotations

import os
from typing import Dict, List

import requests

from .models import Issue


class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        if not self.token:
            raise RuntimeError("Missing GITHUB_TOKEN environment variable.")
        self.base = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "oss-issue-fixer-agent",
            }
        )

    def _get(self, path: str, params: Dict | None = None):
        try:
            resp = self.session.get(f"{self.base}{path}", params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"GitHub GET failed: {path}: {exc}") from exc

    def _post(self, path: str, payload: Dict | None = None):
        try:
            resp = self.session.post(
                f"{self.base}{path}", json=payload or {}, timeout=60
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"GitHub POST failed: {path}: {exc}") from exc

    def _patch(self, path: str, payload: Dict | None = None):
        try:
            resp = self.session.patch(
                f"{self.base}{path}", json=payload or {}, timeout=60
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise RuntimeError(f"GitHub PATCH failed: {path}: {exc}") from exc

    def current_user(self) -> Dict:
        return self._get("/user")

    def list_open_issues(
        self, repo: str, labels_any: List[str], per_page: int = 30
    ) -> List[Issue]:
        payload = self._get(
            f"/repos/{repo}/issues",
            params={
                "state": "open",
                "sort": "updated",
                "direction": "desc",
                "per_page": per_page,
            },
        )
        issues: List[Issue] = []
        for item in payload:
            issues.append(
                Issue(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body") or "",
                    html_url=item["html_url"],
                    labels=[lab["name"] for lab in item.get("labels", [])],
                    is_pull_request="pull_request" in item,
                )
            )
        if not labels_any:
            return issues
        wanted = {x.lower() for x in labels_any}
        filtered: List[Issue] = []
        for issue in issues:
            labels = {x.lower() for x in issue.labels}
            if labels.intersection(wanted):
                filtered.append(issue)
        return filtered

    def get_file_text(self, repo: str, path: str) -> str:
        # NOTE: contents API returns base64 for JSON, but raw endpoint is simpler.
        owner, name = repo.split("/", 1)
        raw_url = (
            f"https://raw.githubusercontent.com/{owner}/{name}/HEAD/{path}"
        )
        resp = self.session.get(raw_url, timeout=60)
        if resp.status_code != 200:
            return ""
        return resp.text

    def ensure_fork(self, upstream_repo: str) -> Dict:
        try:
            return self._post(f"/repos/{upstream_repo}/forks")
        except RuntimeError as exc:
            cause = exc.__cause__
            if isinstance(cause, requests.HTTPError) and cause.response is not None and cause.response.status_code == 422:
                me = self.current_user()["login"]
                repo_name = upstream_repo.split("/", 1)[1]
                return self._get(f"/repos/{me}/{repo_name}")
            raise
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 422:
                me = self.current_user()["login"]
                repo_name = upstream_repo.split("/", 1)[1]
                return self._get(f"/repos/{me}/{repo_name}")
            raise

    def create_pull_request(
        self,
        upstream_repo: str,
        base_branch: str,
        head_ref: str,
        title: str,
        body: str,
    ) -> Dict:
        return self._post(
            f"/repos/{upstream_repo}/pulls",
            {
                "title": title,
                "body": body,
                "base": base_branch,
                "head": head_ref,
            },
        )

    def get_default_branch(self, repo: str) -> str:
        data = self._get(f"/repos/{repo}")
        return data["default_branch"]
