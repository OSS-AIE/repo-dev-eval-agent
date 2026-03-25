from __future__ import annotations

import subprocess
from pathlib import Path

from oss_issue_fixer.repo_eval_agent import RepoEvalAgent, _normalize_host_command
from oss_issue_fixer.repo_eval_models import (
    LocalEvalConfig,
    RepoEvalAppConfig,
    RepoEvalPolicy,
)


def test_collect_pr_metrics_uses_git_remote_to_detect_gitcode(tmp_path: Path):
    subprocess.run("git init", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        "git remote add origin https://gitcode.com/Ascend/MindIE-SD.git",
        cwd=tmp_path,
        shell=True,
        check=True,
    )

    agent = RepoEvalAgent(
        cfg=RepoEvalAppConfig(enable_local_commands=False),
        disable_ai=True,
    )
    repo = RepoEvalPolicy(
        name="Ascend/MindIE-SD",
        local_path=str(tmp_path),
    )

    metrics = agent._collect_pr_metrics(
        repo=repo,
        repo_path=tmp_path,
        ai_review_signals=[],
        errors=[],
    )

    assert metrics.remote_platform == "gitcode"
    assert "GITCODE_TOKEN" in metrics.collection_note


def test_collect_gitcode_pr_metrics_detects_robot_comments(monkeypatch, tmp_path: Path):
    subprocess.run("git init", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        "git remote add origin https://gitcode.com/Ascend/MindIE-SD.git",
        cwd=tmp_path,
        shell=True,
        check=True,
    )

    class FakeGitCodeClient:
        token = "token"

        def __init__(self, token_env: str = "GITCODE_TOKEN"):
            self.token_env = token_env

        def list_recent_pulls(self, repo: str, per_page: int):
            return [{"number": 215, "updated_at": "2026-03-20T08:00:00Z"}]

        def list_pull_comments(self, repo: str, pull_number: int):
            return [
                {
                    "body": "建议修复空指针检查",
                    "user": {"name": "ascend-robot"},
                }
            ]

    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_agent.RepoEvalGitCodeClient",
        FakeGitCodeClient,
    )

    agent = RepoEvalAgent(
        cfg=RepoEvalAppConfig(enable_local_commands=False),
        disable_ai=True,
    )
    repo = RepoEvalPolicy(name="Ascend/MindIE-SD", local_path=str(tmp_path))
    repo.github.ai_review_author_markers = ["ascend-robot"]
    repo.github.pr_window_days = 30

    metrics = agent._collect_pr_metrics(
        repo=repo,
        repo_path=tmp_path,
        ai_review_signals=[],
        errors=[],
    )

    assert metrics.remote_platform == "gitcode"
    assert metrics.ai_review_supported is True
    assert any("ascend-robot" in item for item in metrics.ai_review_evidence)
    assert "last 30 days" in metrics.collection_note


def test_collect_github_pr_metrics_filters_by_window_and_counts_average(
    monkeypatch,
    tmp_path: Path,
):
    subprocess.run("git init", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        "git remote add origin https://github.com/example/project.git",
        cwd=tmp_path,
        shell=True,
        check=True,
    )

    class FakeGitHubClient:
        def __init__(self, token_env: str = "GITHUB_TOKEN"):
            self.token_env = token_env

        def list_workflow_runs(self, repo: str, event: str, per_page: int):
            return [
                {
                    "id": 100,
                    "name": "PR",
                    "event": "pull_request",
                    "run_started_at": "2026-03-22T10:00:00Z",
                    "updated_at": "2026-03-22T10:10:00Z",
                    "created_at": "2026-03-22T10:00:00Z",
                },
                {
                    "id": 101,
                    "name": "PR",
                    "event": "pull_request",
                    "run_started_at": "2026-02-01T10:00:00Z",
                    "updated_at": "2026-02-01T10:40:00Z",
                    "created_at": "2026-02-01T10:00:00Z",
                },
            ]

        def list_workflow_jobs(self, repo: str, run_id: int, per_page: int = 100):
            if run_id != 100:
                return []
            return [
                {
                    "labels": ["ubuntu-latest"],
                    "started_at": "2026-03-22T10:00:00Z",
                    "completed_at": "2026-03-22T10:10:00Z",
                }
            ]

        def list_recent_pulls(self, repo: str, per_page: int):
            return [{"number": 12, "updated_at": "2026-03-22T11:00:00Z"}]

        def list_reviews(self, repo: str, pull_number: int):
            return [{"user": {"login": "coderabbitai[bot]"}, "body": "nit"}]

        def list_issue_comments(self, repo: str, pull_number: int):
            return []

    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_agent.RepoEvalGitHubClient",
        FakeGitHubClient,
    )

    agent = RepoEvalAgent(
        cfg=RepoEvalAppConfig(enable_local_commands=False),
        disable_ai=True,
    )
    repo = RepoEvalPolicy(name="example/project", local_path=str(tmp_path))
    repo.github.pr_window_days = 30

    metrics = agent._collect_pr_metrics(
        repo=repo,
        repo_path=tmp_path,
        ai_review_signals=[],
        errors=[],
    )

    assert metrics.remote_platform == "github"
    assert metrics.workflow_run_count == 1
    assert metrics.sampled_pull_count == 1
    assert metrics.average_duration_sec == 600.0
    assert metrics.estimated_cpu_core_minutes == 40.0
    assert metrics.ai_review_supported is True
    assert any("coderabbitai" in item for item in metrics.ai_review_evidence)


def test_normalize_host_command_translates_unix_env_prefix():
    command = (
        "VLLM_USE_PRECOMPILED=1 UV_INDEX=https://example.invalid uv pip install -e ."
    )
    normalized = _normalize_host_command(command)

    assert "$env:VLLM_USE_PRECOMPILED='1'" in normalized
    assert "$env:UV_INDEX='https://example.invalid'" in normalized
    assert normalized.endswith("uv pip install -e .")


def test_run_local_command_records_timeout_duration(tmp_path: Path):
    agent = RepoEvalAgent(
        cfg=RepoEvalAppConfig(enable_local_commands=True),
        disable_ai=True,
    )

    result = agent._run_local_command(
        repo_path=tmp_path,
        command='python -c "import time; time.sleep(2)"',
        local_cfg=LocalEvalConfig(runner="host"),
        timeout_sec=1,
        run_twice=False,
    )

    assert result.status == "timeout"
    assert result.duration_sec is not None
    assert result.duration_sec >= 1.0
