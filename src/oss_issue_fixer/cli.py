from __future__ import annotations

import argparse

from .agent import FixerAgent
from .config import load_config
from .scheduler import run_daily


def main() -> None:
    parser = argparse.ArgumentParser(prog="oss-fixer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    once = sub.add_parser("run-once")
    once.add_argument("--config", required=True)
    once.add_argument("--max-prs", type=int, default=None)
    once.add_argument("--dry-run", action="store_true")

    daily = sub.add_parser("run-daily")
    daily.add_argument("--config", required=True)
    daily.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    cfg = load_config(args.config)
    agent = FixerAgent(cfg, dry_run=args.dry_run)

    if args.cmd == "run-once":
        res = agent.run_once(args.max_prs)
        print(
            f"run-once done: scanned={res.scanned}, attempted={res.attempted}, "
            f"submitted={res.submitted}, skipped={res.skipped}"
        )
        return
    run_daily(agent)


if __name__ == "__main__":
    main()
