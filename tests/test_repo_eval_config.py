from __future__ import annotations

from pathlib import Path

from oss_issue_fixer.repo_eval_config import load_repo_eval_config


def test_load_repo_eval_config(tmp_path: Path):
    config_path = tmp_path / "repo_eval.yaml"
    config_path.write_text(
        """
workspace_root: .work/eval
report_root: reports/eval
recent_pr_limit: 5
enable_local_commands: false
repos:
  - name: example/project
    local_path: D:\\repo
    local:
      unit_test_command: pytest -q
      code_check_command: pre-commit run -a
      runner: wsl
      wsl_distro: Ubuntu
      refresh_local_repo: false
      documentation_refs: [origin/master]
    ai:
      enabled: true
      provider: codex
      command: codex.cmd
    github:
      pr_window_days: 14
      github_token_env: MY_GITHUB_TOKEN
      gitcode_token_env: MY_GITCODE_TOKEN
      ai_review_author_markers: [ascend-robot]
""".strip(),
        encoding="utf-8",
    )

    cfg = load_repo_eval_config(str(config_path))
    assert cfg.recent_pr_limit == 5
    assert len(cfg.repos) == 1
    assert cfg.repos[0].name == "example/project"
    assert cfg.repos[0].local.unit_test_command == "pytest -q"
    assert cfg.repos[0].local.code_check_command == "pre-commit run -a"
    assert cfg.repos[0].local.runner == "wsl"
    assert cfg.repos[0].local.wsl_distro == "Ubuntu"
    assert cfg.repos[0].local.refresh_local_repo is False
    assert cfg.repos[0].local.documentation_refs == ["origin/master"]
    assert cfg.repos[0].ai.provider == "codex"
    assert cfg.repos[0].github.pr_window_days == 14
    assert cfg.repos[0].github.github_token_env == "MY_GITHUB_TOKEN"
    assert cfg.repos[0].github.gitcode_token_env == "MY_GITCODE_TOKEN"
    assert cfg.repos[0].github.ai_review_author_markers == ["ascend-robot"]
