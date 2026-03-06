from __future__ import annotations

import argparse
import json
from pathlib import Path

from oss_issue_fixer.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--report-json", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    report = json.loads(Path(args.report_json).read_text(encoding="utf-8-sig"))
    total = int(report.get("total_prs", 0))
    target = int(cfg.daily_target_prs)
    print(f"daily prs: {total}, target: {target}")
    if total < target:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
