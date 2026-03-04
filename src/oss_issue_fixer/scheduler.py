from __future__ import annotations

import time
from datetime import datetime, timedelta

from .agent import FixerAgent


def run_daily(agent: FixerAgent) -> None:
    while True:
        result = agent.run_once()
        print(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            f"scanned={result.scanned} attempted={result.attempted} "
            f"submitted={result.submitted} skipped={result.skipped}"
        )
        next_run = datetime.now() + timedelta(days=1)
        sleep_seconds = max(60, int((next_run - datetime.now()).total_seconds()))
        time.sleep(sleep_seconds)
