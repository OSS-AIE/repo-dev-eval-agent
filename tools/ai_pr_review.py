from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import requests

COMMENT_MARKER = "<!-- oss-aie-ai-review -->"
MAX_DIFF_CHARS = 120_000
MAX_FILES = 80


@dataclass
class GitHubContext:
    repo: str
    pr_number: int
    api_url: str
    server_url: str
    token: str


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _github_headers(
    token: str, *, accept: str = "application/vnd.github+json"
) -> dict[str, str]:
    return {
        "Accept": accept,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "repo-dev-eval-agent",
    }


def _must_context() -> GitHubContext:
    repo = _env("GITHUB_REPOSITORY")
    api_url = _env("GITHUB_API_URL", "https://api.github.com")
    server_url = _env("GITHUB_SERVER_URL", "https://github.com")
    token = _env("GITHUB_TOKEN")
    pr_number = _env("PR_NUMBER")
    if not repo or not token or not pr_number:
        raise RuntimeError(
            "missing required GitHub context: GITHUB_REPOSITORY, GITHUB_TOKEN, PR_NUMBER"
        )
    return GitHubContext(
        repo=repo,
        pr_number=int(pr_number),
        api_url=api_url,
        server_url=server_url,
        token=token,
    )


def _github_get(
    context: GitHubContext, path: str, *, accept: str = "application/vnd.github+json"
) -> Any:
    response = requests.get(
        f"{context.api_url}{path}",
        headers=_github_headers(context.token, accept=accept),
        timeout=60,
    )
    response.raise_for_status()
    if "application/json" in response.headers.get("Content-Type", ""):
        return response.json()
    return response.text


def _github_post(context: GitHubContext, path: str, payload: dict[str, Any]) -> Any:
    response = requests.post(
        f"{context.api_url}{path}",
        headers=_github_headers(context.token),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _github_patch(context: GitHubContext, path: str, payload: dict[str, Any]) -> Any:
    response = requests.patch(
        f"{context.api_url}{path}",
        headers=_github_headers(context.token),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _openai_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _extract_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    texts: list[str] = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(str(content["text"]).strip())
    return "\n".join(text for text in texts if text).strip()


def _fetch_pr_snapshot(context: GitHubContext) -> dict[str, Any]:
    pr = _github_get(context, f"/repos/{context.repo}/pulls/{context.pr_number}")
    files = _github_get(
        context,
        f"/repos/{context.repo}/pulls/{context.pr_number}/files?per_page={MAX_FILES}",
    )
    diff = _github_get(
        context,
        f"/repos/{context.repo}/pulls/{context.pr_number}",
        accept="application/vnd.github.v3.diff",
    )
    if isinstance(diff, str) and len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n[diff truncated]"
    return {"pr": pr, "files": files, "diff": diff}


def _build_openai_prompt(
    snapshot: dict[str, Any], context: GitHubContext
) -> list[dict[str, Any]]:
    pr = snapshot["pr"]
    changed_files = [
        {
            "filename": item.get("filename"),
            "status": item.get("status"),
            "additions": item.get("additions"),
            "deletions": item.get("deletions"),
        }
        for item in snapshot.get("files", []) or []
        if isinstance(item, dict)
    ]
    prompt = {
        "repo": context.repo,
        "pull_request": {
            "number": pr.get("number"),
            "title": pr.get("title"),
            "body": pr.get("body"),
            "base": pr.get("base", {}).get("ref"),
            "head": pr.get("head", {}).get("ref"),
            "author": pr.get("user", {}).get("login"),
            "html_url": pr.get("html_url"),
        },
        "changed_files": changed_files,
        "diff": snapshot["diff"],
    }
    system = (
        "You are reviewing a pull request for a Python repository.\n"
        "Return a concise GitHub review comment in Simplified Chinese.\n"
        "Focus on correctness, regressions, missing tests, workflow risk, and maintainability.\n"
        "If no concrete issue is found, say so explicitly.\n"
        "Format:\n"
        "## 总体判断\n"
        "- one short bullet\n"
        "## 发现\n"
        "- 0 to 5 bullets, each with severity prefix like [高]/[中]/[低]\n"
        "## 建议\n"
        "- 1 to 3 actionable bullets\n"
        "Keep the response under 350 Chinese characters when possible."
    )
    user = json.dumps(prompt, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": [{"type": "input_text", "text": system}]},
        {"role": "user", "content": [{"type": "input_text", "text": user}]},
    ]


def _request_ai_review(snapshot: dict[str, Any], context: GitHubContext) -> str:
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        return ""
    base_url = _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = _env("OPENAI_MODEL", "gpt-5-mini")
    payload = {
        "model": model,
        "input": _build_openai_prompt(snapshot, context),
        "reasoning": {"effort": "low"},
    }
    response = requests.post(
        f"{base_url}/responses",
        headers=_openai_headers(api_key),
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    text = _extract_output_text(data)
    if not text:
        raise RuntimeError("OpenAI response did not include output_text")
    return text


def _existing_comment_id(context: GitHubContext) -> int | None:
    comments = _github_get(
        context,
        f"/repos/{context.repo}/issues/{context.pr_number}/comments?per_page=100",
    )
    for comment in comments or []:
        if not isinstance(comment, dict):
            continue
        body = str(comment.get("body") or "")
        if COMMENT_MARKER in body:
            return int(comment["id"])
    return None


def _publish_comment(context: GitHubContext, body: str) -> None:
    comment_id = _existing_comment_id(context)
    payload = {"body": body}
    if comment_id is None:
        _github_post(
            context,
            f"/repos/{context.repo}/issues/{context.pr_number}/comments",
            payload,
        )
        return
    _github_patch(
        context, f"/repos/{context.repo}/issues/comments/{comment_id}", payload
    )


def main() -> int:
    try:
        context = _must_context()
        if not _env("OPENAI_API_KEY"):
            print("OPENAI_API_KEY is not configured; skipping AI review comment.")
            return 0
        snapshot = _fetch_pr_snapshot(context)
        review = _request_ai_review(snapshot, context)
        pr_url = snapshot["pr"].get("html_url", "")
        body = f"{COMMENT_MARKER}\n## AI 辅助代码检视\n- PR: {pr_url}\n\n{review}\n"
        _publish_comment(context, body)
        print("AI review comment published.")
        return 0
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"AI review failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
