from __future__ import annotations

from .github_api import GitHubClient


def load_contributing_excerpt(gh: GitHubClient, repo: str, max_chars: int = 8000) -> str:
    for path in ("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"):
        content = gh.get_file_text(repo, path)
        if content:
            return content[:max_chars]
    return ""
