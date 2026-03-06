from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

import requests

from oss_issue_fixer.config import load_config


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def search_prs(token: str, query: str) -> list[dict]:
    items: list[dict] = []
    page = 1
    while page <= 10:
        resp = requests.get(
            "https://api.github.com/search/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "oss-issue-fixer-agent",
            },
            params={"q": query, "sort": "created", "order": "desc", "per_page": 100, "page": page},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-output", required=True)
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN")

    cfg = load_config(args.config)
    since = utc_now() - dt.timedelta(hours=args.window_hours)
    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Use authenticated account as author.
    me_resp = requests.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "oss-issue-fixer-agent",
        },
        timeout=30,
    )
    me_resp.raise_for_status()
    login = me_resp.json()["login"]

    rows: list[dict] = []
    total = 0
    for repo in cfg.repos:
        q = f"repo:{repo.name} is:pr author:{login} created:>={since_str}"
        prs = search_prs(token, q)
        total += len(prs)
        rows.append(
            {
                "repo": repo.name,
                "count": len(prs),
                "prs": [
                    {
                        "number": item["number"],
                        "title": item["title"],
                        "url": item["html_url"],
                        "created_at": item["created_at"],
                    }
                    for item in prs[:30]
                ],
            }
        )

    payload = {
        "generated_at_utc": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": args.window_hours,
        "target_prs": cfg.daily_target_prs,
        "author": login,
        "total_prs": total,
        "repos": rows,
    }

    md_lines = [
        "# Daily PR Report",
        "",
        f"- Author: `{login}`",
        f"- Window: last `{args.window_hours}` hours",
        f"- Generated (UTC): `{payload['generated_at_utc']}`",
        f"- Target: `{cfg.daily_target_prs}`",
        f"- Total PRs: `{total}`",
        "",
    ]
    for row in rows:
        md_lines.append(f"## {row['repo']}")
        md_lines.append(f"- PR count: `{row['count']}`")
        for pr in row["prs"][:10]:
            md_lines.append(f"- #{pr['number']} {pr['title']} ({pr['url']})")
        md_lines.append("")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(md_lines), encoding="utf-8")
    Path(args.json_output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
