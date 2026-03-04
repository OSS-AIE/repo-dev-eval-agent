from pathlib import Path

from oss_issue_fixer.config import load_config


def test_load_config():
    cfg = load_config(str(Path("config/repos.yaml")))
    assert cfg.daily_target_prs == 10
    assert len(cfg.repos) >= 4
    assert cfg.repos[0].name
