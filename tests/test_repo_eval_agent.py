from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
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
            recent = datetime.now(timezone.utc) - timedelta(days=2)
            return [{"number": 215, "updated_at": recent.isoformat()}]

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
    assert "workflow 时长与资源指标暂未接入" in metrics.collection_note


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
            recent = datetime.now(timezone.utc) - timedelta(days=2)
            old = datetime.now(timezone.utc) - timedelta(days=60)
            return [
                {
                    "id": 100,
                    "name": "PR",
                    "event": "pull_request",
                    "run_started_at": recent.isoformat(),
                    "updated_at": (recent + timedelta(minutes=10)).isoformat(),
                    "created_at": recent.isoformat(),
                },
                {
                    "id": 101,
                    "name": "PR",
                    "event": "pull_request",
                    "run_started_at": old.isoformat(),
                    "updated_at": (old + timedelta(minutes=40)).isoformat(),
                    "created_at": old.isoformat(),
                },
            ]

        def list_workflow_jobs(self, repo: str, run_id: int, per_page: int = 100):
            if run_id != 100:
                return []
            recent = datetime.now(timezone.utc) - timedelta(days=2)
            return [
                {
                    "labels": ["ubuntu-latest"],
                    "started_at": recent.isoformat(),
                    "completed_at": (recent + timedelta(minutes=10)).isoformat(),
                }
            ]

        def list_recent_pulls(self, repo: str, per_page: int):
            recent = datetime.now(timezone.utc) - timedelta(days=2)
            return [{"number": 12, "updated_at": recent.isoformat()}]

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


def test_collect_github_pr_metrics_explains_missing_samples(
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
        token = ""

        def __init__(self, token_env: str = "GITHUB_TOKEN"):
            self.token_env = token_env
            self.token = ""

        def list_workflow_runs(self, repo: str, event: str, per_page: int):
            return []

        def list_workflow_jobs(self, repo: str, run_id: int, per_page: int = 100):
            return []

        def list_recent_pulls(self, repo: str, per_page: int):
            return []

        def list_reviews(self, repo: str, pull_number: int):
            return []

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

    assert metrics.average_duration_sec is None
    assert "匿名访问" in metrics.collection_note
    assert "没有可用的 GitHub Actions workflow 样本" in metrics.collection_note
    assert "没有可用的 PR 样本" in metrics.collection_note


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


def test_run_local_command_runs_setup_once_and_reuses_environment(tmp_path: Path):
    agent = RepoEvalAgent(
        cfg=RepoEvalAppConfig(enable_local_commands=True),
        disable_ai=True,
    )
    marker = tmp_path / "setup.txt"

    first = agent._run_local_command(
        repo_path=tmp_path,
        command="python -c \"from pathlib import Path; print(Path('setup.txt').read_text().strip())\"",
        local_cfg=LocalEvalConfig(runner="host"),
        timeout_sec=30,
        run_twice=False,
        setup_command=(
            'python -c "from pathlib import Path; '
            "p=Path('setup.txt'); "
            "p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')\""
        ),
    )

    second = agent._run_local_command(
        repo_path=tmp_path,
        command="python -c \"from pathlib import Path; print(Path('setup.txt').read_text().strip())\"",
        local_cfg=LocalEvalConfig(runner="host"),
        timeout_sec=30,
        run_twice=False,
        setup_command=(
            'python -c "from pathlib import Path; '
            "p=Path('setup.txt'); "
            "p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')\""
        ),
    )

    assert first.status == "ok"
    assert first.setup_status == "ok"
    assert second.status == "ok"
    assert second.setup_status == "reused"
    assert marker.read_text(encoding="utf-8") == "1"


def test_run_local_command_uses_setup_result_when_command_is_already_in_setup(
    tmp_path: Path,
):
    agent = RepoEvalAgent(
        cfg=RepoEvalAppConfig(enable_local_commands=True),
        disable_ai=True,
    )

    result = agent._run_local_command(
        repo_path=tmp_path,
        command="python -c \"print('build')\"",
        local_cfg=LocalEvalConfig(runner="host"),
        timeout_sec=30,
        run_twice=True,
        setup_command="python -c \"print('build')\"",
    )

    assert result.status == "ok"
    assert result.returncode == 0
    assert result.setup_status == "ok"
    assert "build" in result.stdout_excerpt


def test_evaluate_repo_uses_skill_local_overrides(monkeypatch, tmp_path: Path):
    (tmp_path / "README.md").write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_agent.scan_repository",
        lambda repo_path, documentation_refs=None, repo_name="": __import__(
            "oss_issue_fixer.repo_eval_models", fromlist=["StaticAnalysisResult"]
        ).StaticAnalysisResult(),
    )
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_agent.infer_local_commands",
        lambda repo_path, result: None,
    )
    monkeypatch.setattr(
        RepoEvalAgent,
        "_collect_pr_metrics",
        lambda self, repo, repo_path, ai_review_signals, errors: __import__(
            "oss_issue_fixer.repo_eval_models", fromlist=["PullRequestMetrics"]
        ).PullRequestMetrics(),
    )
    captured: list[tuple[str, str, str]] = []

    def fake_run(
        self,
        repo_path,
        command,
        local_cfg,
        timeout_sec,
        run_twice,
        setup_command="",
        command_prefix="",
    ):
        captured.append((command, setup_command, command_prefix))
        return __import__(
            "oss_issue_fixer.repo_eval_models", fromlist=["CommandExecutionResult"]
        ).CommandExecutionResult(status="disabled", command=command)

    monkeypatch.setattr(RepoEvalAgent, "_run_local_command", fake_run)

    agent = RepoEvalAgent(
        cfg=RepoEvalAppConfig(
            enable_local_commands=False,
            repos=[
                RepoEvalPolicy(
                    name="vllm-project/vllm",
                    local_path=str(tmp_path),
                    local=LocalEvalConfig(runner="wsl", refresh_local_repo=False),
                )
            ],
        ),
        disable_ai=True,
    )

    result = agent.evaluate_repo(agent.cfg.repos[0])

    assert result.repo == "vllm-project/vllm"
    assert any(
        command
        == "python -m pytest tests/v1/structured_output/test_backend_xgrammar.py -q"
        and "uv venv --python 3.12 --seed .venv" in setup_command
        and command_prefix == "source .venv/bin/activate"
        for command, setup_command, command_prefix in captured
    )


def test_resolve_repo_refreshes_remote_matching_clone_url(monkeypatch, tmp_path: Path):
    subprocess.run("git init", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        "git remote add origin https://github.com/robellliu-dev/oss-issue-fixer-agent.git",
        cwd=tmp_path,
        shell=True,
        check=True,
    )
    subprocess.run(
        "git remote add ossaie https://github.com/OSS-AIE/repo-dev-eval-agent.git",
        cwd=tmp_path,
        shell=True,
        check=True,
    )

    seen_args: list[list[str]] = []
    real_git_run = __import__(
        "oss_issue_fixer.repo_eval_agent", fromlist=["_git_run"]
    )._git_run

    def fake_git_run(repo_path: Path, args: list[str], timeout: int = 60):
        seen_args.append(args)
        return real_git_run(repo_path, args, timeout)

    monkeypatch.setattr("oss_issue_fixer.repo_eval_agent._git_run", fake_git_run)

    agent = RepoEvalAgent(
        cfg=RepoEvalAppConfig(enable_local_commands=False),
        disable_ai=True,
    )
    repo = RepoEvalPolicy(
        name="OSS-AIE/repo-dev-eval-agent",
        local_path=str(tmp_path),
        clone_url="https://github.com/OSS-AIE/repo-dev-eval-agent.git",
    )
    errors: list[str] = []

    resolved = agent._resolve_repo(repo, errors)

    assert resolved == tmp_path.resolve()
    assert ["fetch", "ossaie", "--prune"] in seen_args
