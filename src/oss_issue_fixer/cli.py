from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import FixerAgent
from .config import load_config
from .scheduler import run_daily
from .smoke import run_local_smoke


def main() -> None:
    parser = argparse.ArgumentParser(prog="oss-fixer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    once = sub.add_parser("run-once")
    once.add_argument("--config", required=True)
    once.add_argument("--max-prs", type=int, default=None)
    once.add_argument("--dry-run", action="store_true")
    once.add_argument("--repo", action="append", default=[])
    once.add_argument("--result-json", default="")

    daily = sub.add_parser("run-daily")
    daily.add_argument("--config", required=True)
    daily.add_argument("--dry-run", action="store_true")

    smoke = sub.add_parser("run-local-smoke")
    smoke.add_argument("--config", required=True)
    smoke.add_argument("--repo", required=True)
    smoke.add_argument("--issue-number", type=int, default=999999)
    smoke.add_argument("--issue-title", default="Local smoke test issue")
    smoke.add_argument("--issue-body", default="Validate local end-to-end fixer flow.")
    smoke.add_argument("--skip-checks", action="store_true")

    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.cmd == "run-local-smoke":
        res = run_local_smoke(
            cfg=cfg,
            repo_name=args.repo,
            issue_number=args.issue_number,
            issue_title=args.issue_title,
            issue_body=args.issue_body,
            skip_checks=args.skip_checks,
        )
        print(
            "local-smoke done: "
            f"repo={res.repo} issue={res.issue_number} changed={res.changed} "
            f"checks_passed={res.checks_passed} branch={res.branch} worktree={res.worktree}"
        )
        return

    try:
        agent = FixerAgent(cfg, dry_run=args.dry_run)
    except Exception as exc:
        print(f"failed to initialize agent: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if args.cmd == "run-once":
        allow = set(args.repo) if args.repo else None
        res = agent.run_once(args.max_prs, repo_allowlist=allow)
        print(
            f"run-once done: scanned={res.scanned}, attempted={res.attempted}, "
            f"submitted={res.submitted}, skipped={res.skipped}"
        )
        if args.result_json:
            payload = {
                "scanned": res.scanned,
                "attempted": res.attempted,
                "submitted": res.submitted,
                "skipped": res.skipped,
            }
            Path(args.result_json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return
    run_daily(agent)


if __name__ == "__main__":
    main()
