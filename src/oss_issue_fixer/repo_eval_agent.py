from __future__ import annotations

import re
import shlex
import statistics
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .git_ops import ensure_repo
from .repo_eval_ai import summarize_with_ai
from .repo_eval_docs import analyze_documentation_quality
from .repo_eval_gitcode import RepoEvalGitCodeClient
from .repo_eval_github import RepoEvalGitHubClient
from .repo_eval_models import (
    CommandExecutionResult,
    LocalEvalConfig,
    PullRequestMetrics,
    RepoEvalAppConfig,
    RepoEvalPolicy,
    RepoEvaluationResult,
    RunnerCapacity,
)
from .repo_eval_scan import infer_local_commands, scan_repository

DEFAULT_AI_REVIEW_MARKERS = (
    "copilot",
    "coderabbit",
    "qodo",
    "codex",
    "gemini",
    "openai",
    "robot",
)

DEFAULT_RUNNER_CAPACITY = {
    "ubuntu-latest": RunnerCapacity(vcpus=4),
    "ubuntu-24.04": RunnerCapacity(vcpus=4),
    "ubuntu-22.04": RunnerCapacity(vcpus=4),
    "ubuntu-20.04": RunnerCapacity(vcpus=4),
    "windows-latest": RunnerCapacity(vcpus=4),
    "windows-2022": RunnerCapacity(vcpus=4),
    "windows-2019": RunnerCapacity(vcpus=4),
    "macos-latest": RunnerCapacity(vcpus=3),
    "macos-14": RunnerCapacity(vcpus=3),
    "macos-13": RunnerCapacity(vcpus=3),
}

ENV_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _infer_remote_platform(repo: RepoEvalPolicy) -> str:
    raw = f"{repo.clone_url} {repo.local_path} {repo.name}".lower()
    if "gitcode.com" in raw:
        return "gitcode"
    return "github"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _duration_seconds(start: str | None, end: str | None) -> float | None:
    left = _parse_ts(start)
    right = _parse_ts(end)
    if left is None or right is None:
        return None
    return max(0.0, (right - left).total_seconds())


def _excerpt(text: str, limit: int = 400) -> str:
    return (text or "").strip().replace("\r", " ").replace("\n", " ")[:limit]


def _repo_local_dir(workspace_root: Path, repo_name: str) -> Path:
    return workspace_root / repo_name.replace("/", "__")


def _git_remote_origin(repo_path: Path) -> str:
    try:
        proc = subprocess.run(
            "git remote get-url origin",
            cwd=str(repo_path),
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=10,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _git_remote_urls(repo_path: Path) -> dict[str, str]:
    rc, stdout, _ = _git_run(repo_path, ["remote"])
    if rc != 0:
        origin = _git_remote_origin(repo_path)
        return {"origin": origin} if origin else {}

    remotes: dict[str, str] = {}
    for remote_name in stdout.splitlines():
        name = remote_name.strip()
        if not name:
            continue
        rc, remote_stdout, _ = _git_run(repo_path, ["remote", "get-url", name])
        if rc != 0:
            continue
        url = remote_stdout.strip()
        if url:
            remotes[name] = url
    return remotes


def _preferred_fetch_remote_name(repo_path: Path, preferred_url: str = "") -> str:
    remotes = _git_remote_urls(repo_path)
    if not remotes:
        return ""
    if preferred_url:
        for name, remote_url in remotes.items():
            if remote_url == preferred_url:
                return name
    return "origin" if "origin" in remotes else next(iter(remotes))


def _git_run(
    repo_path: Path, args: list[str], timeout: int = 60
) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _git_is_repo(repo_path: Path) -> bool:
    return (repo_path / ".git").exists() or (repo_path / ".gitcode").exists()


def _git_ref_exists(repo_path: Path, ref: str) -> bool:
    rc, _, _ = _git_run(repo_path, ["rev-parse", "--verify", ref])
    return rc == 0


def _git_remote_default_ref(repo_path: Path) -> str:
    rc, stdout, _ = _git_run(
        repo_path,
        ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
    )
    ref = stdout.strip()
    if rc == 0 and ref:
        return ref
    for candidate in ("origin/master", "origin/main"):
        if _git_ref_exists(repo_path, candidate):
            return candidate
    return ""


def _window_start(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(0, days))


def _in_window(value: str | None, days: int) -> bool:
    timestamp = _parse_ts(value)
    if timestamp is None:
        return False
    return timestamp >= _window_start(days)


def _comment_author(payload: dict[str, Any]) -> str:
    user = payload.get("user") or {}
    for key in ("login", "username", "name", "nick_name"):
        value = user.get(key) if isinstance(user, dict) else ""
        if value:
            return str(value)
    for key in ("author", "username", "user_name", "name"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _comment_body(payload: dict[str, Any]) -> str:
    for key in ("body", "note", "content", "message"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _ai_review_markers(repo: RepoEvalPolicy) -> tuple[str, ...]:
    extra = tuple((item or "").lower() for item in repo.github.ai_review_author_markers)
    return tuple(dict.fromkeys(DEFAULT_AI_REVIEW_MARKERS + extra))


def _looks_like_ai_review(
    author: str,
    body: str,
    markers: tuple[str, ...],
) -> bool:
    lowered_author = (author or "").lower()
    lowered_body = (body or "").lower()
    if any(marker and marker in lowered_author for marker in markers):
        return True
    if any(token in lowered_author for token in ("-bot", "_bot", " bot", "robot")):
        return any(
            token in lowered_body
            for token in (
                "review",
                "comment",
                "suggest",
                "建议",
                "lint",
                "style",
                "代码",
                "检测",
            )
        )
    return False


def _windows_to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[-1].lstrip("/")
    return f"/mnt/{drive}/{tail}"


def _normalize_host_command(command: str) -> str:
    stripped = (command or "").strip()
    if not stripped:
        return stripped

    parts = stripped.split()
    assignments: list[tuple[str, str]] = []
    remainder_index = 0
    for token in parts:
        match = ENV_ASSIGNMENT_RE.match(token)
        if not match:
            break
        assignments.append((match.group(1), match.group(2)))
        remainder_index += 1

    if not assignments:
        return stripped

    remainder = " ".join(parts[remainder_index:]).strip()
    if not remainder:
        return stripped
    prefix = "; ".join(f"$env:{name}='{value}'" for name, value in assignments)
    return f"{prefix}; {remainder}"


class RepoEvalAgent:
    def __init__(
        self,
        cfg: RepoEvalAppConfig,
        enable_local_commands_override: bool | None = None,
        disable_ai: bool = False,
    ):
        self.cfg = cfg
        self.workspace_root = Path(cfg.workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.enable_local_commands = (
            cfg.enable_local_commands
            if enable_local_commands_override is None
            else enable_local_commands_override
        )
        self.disable_ai = disable_ai

    def run(self, repo_allowlist: set[str] | None = None) -> list[RepoEvaluationResult]:
        results: list[RepoEvaluationResult] = []
        for repo in self.cfg.repos:
            if repo_allowlist and repo.name not in repo_allowlist:
                continue
            results.append(self.evaluate_repo(repo))
        return results

    def evaluate_repo(self, repo: RepoEvalPolicy) -> RepoEvaluationResult:
        errors: list[str] = []
        repo_path = self._resolve_repo(repo, errors)
        static = scan_repository(
            repo_path,
            documentation_refs=self._documentation_refs(repo_path, repo.local),
        )
        if self.cfg.enable_command_inference:
            infer_local_commands(repo_path, static)

        build_command = repo.local.incremental_build_command or repo.local.build_command
        if not build_command:
            build_command = static.inferred_build_command
        unit_test_command = (
            repo.local.unit_test_command or static.inferred_unit_test_command
        )
        code_check_command = (
            repo.local.code_check_command or static.inferred_code_check_command
        )

        incremental_build = self._run_local_command(
            repo_path,
            build_command,
            repo.local,
            timeout_sec=repo.local.timeout_sec or self.cfg.default_timeout_sec,
            run_twice=True,
        )
        unit_test = self._run_local_command(
            repo_path,
            unit_test_command,
            repo.local,
            timeout_sec=repo.local.timeout_sec or self.cfg.default_timeout_sec,
            run_twice=False,
        )
        code_check = self._run_local_command(
            repo_path,
            code_check_command,
            repo.local,
            timeout_sec=repo.local.timeout_sec or self.cfg.default_timeout_sec,
            run_twice=False,
        )

        pr_metrics = self._collect_pr_metrics(
            repo,
            repo_path,
            static.ai_review_signals,
            errors,
        )
        result = RepoEvaluationResult(
            repo=repo.name,
            local_path=str(repo_path),
            static=static,
            incremental_build=incremental_build,
            unit_test=unit_test,
            code_check=code_check,
            pr_metrics=pr_metrics,
            errors=errors,
        )
        result.documentation_issues = analyze_documentation_quality(result)
        result.ai_summary = summarize_with_ai(
            repo_path=repo_path,
            policy=repo,
            result=result,
            disable_ai=self.disable_ai,
        )
        return result

    def _documentation_refs(
        self,
        repo_path: Path,
        local_cfg: LocalEvalConfig,
    ) -> list[str]:
        refs = list(local_cfg.documentation_refs)
        if refs:
            return refs
        if not _git_is_repo(repo_path):
            return []
        default_ref = _git_remote_default_ref(repo_path)
        return [default_ref] if default_ref else []

    def _resolve_repo(self, repo: RepoEvalPolicy, errors: list[str]) -> Path:
        if repo.local_path:
            local_path = Path(repo.local_path).resolve()
            if local_path.exists():
                if repo.local.refresh_local_repo and _git_is_repo(local_path):
                    try:
                        fetch_remote = _preferred_fetch_remote_name(
                            local_path, repo.clone_url
                        )
                        fetch_args = ["fetch", fetch_remote, "--prune"]
                        if not fetch_remote:
                            fetch_args = ["fetch", "--all", "--prune"]
                        rc, _, stderr = _git_run(
                            local_path,
                            fetch_args,
                            timeout=300,
                        )
                        if rc != 0:
                            errors.append(
                                f"failed to refresh local repo: {_excerpt(stderr)}"
                            )
                    except Exception as exc:
                        errors.append(f"failed to refresh local repo: {exc}")
                return local_path
            errors.append(f"local_path not found: {local_path}")
        clone_url = repo.clone_url or f"https://github.com/{repo.name}.git"
        local_dir = _repo_local_dir(self.workspace_root, repo.name)
        try:
            ensure_repo(local_dir, clone_url)
        except Exception as exc:
            errors.append(f"failed to clone/fetch repo: {exc}")
        return local_dir

    def _run_local_command(
        self,
        repo_path: Path,
        command: str,
        local_cfg: LocalEvalConfig,
        timeout_sec: int,
        run_twice: bool,
    ) -> CommandExecutionResult:
        if not command:
            return CommandExecutionResult(status="not_configured")
        if not self.enable_local_commands:
            return CommandExecutionResult(status="disabled", command=command)

        runner = (local_cfg.runner or "host").strip().lower()
        timeout_duration_sec: float | None = None

        def build_subprocess_args() -> dict[str, Any]:
            if runner == "wsl":
                wsl_path = _windows_to_wsl_path(repo_path)
                bash_script = (
                    f"set -euo pipefail; cd {shlex.quote(wsl_path)}; {command}"
                )
                args = ["wsl.exe"]
                if local_cfg.wsl_distro:
                    args.extend(["-d", local_cfg.wsl_distro])
                args.extend(["--", "bash", "-lc", bash_script])
                return {
                    "args": args,
                    "cwd": str(repo_path),
                    "shell": False,
                }
            normalized_command = _normalize_host_command(command)
            return {
                "args": normalized_command,
                "cwd": str(repo_path),
                "shell": True,
            }

        def run_once() -> tuple[float, subprocess.CompletedProcess[str]]:
            nonlocal timeout_duration_sec
            start = time.perf_counter()
            proc_args = build_subprocess_args()
            try:
                proc = subprocess.run(
                    proc_args["args"],
                    cwd=proc_args["cwd"],
                    shell=proc_args["shell"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                    timeout=timeout_sec,
                )
            except subprocess.TimeoutExpired:
                timeout_duration_sec = time.perf_counter() - start
                raise
            duration = time.perf_counter() - start
            return duration, proc

        try:
            if run_twice:
                _, _ = run_once()
            duration, proc = run_once()
        except subprocess.TimeoutExpired:
            return CommandExecutionResult(
                status="timeout",
                command=command,
                duration_sec=timeout_duration_sec or float(timeout_sec),
                returncode=None,
                stderr_excerpt=f"timeout after {timeout_sec}s",
            )
        except Exception as exc:
            return CommandExecutionResult(
                status="error",
                command=command,
                stderr_excerpt=str(exc),
            )

        return CommandExecutionResult(
            status="ok" if proc.returncode == 0 else "failed",
            command=command,
            duration_sec=duration,
            returncode=proc.returncode,
            stdout_excerpt=_excerpt(proc.stdout),
            stderr_excerpt=_excerpt(proc.stderr),
        )

    def _runner_capacity_for_job(
        self, repo: RepoEvalPolicy, labels: list[str]
    ) -> RunnerCapacity:
        for label in labels:
            if label in repo.github.runner_capacity_overrides:
                return repo.github.runner_capacity_overrides[label]
            if label in DEFAULT_RUNNER_CAPACITY:
                return DEFAULT_RUNNER_CAPACITY[label]
        if any("npu" in label.lower() or "ascend" in label.lower() for label in labels):
            return RunnerCapacity(vcpus=None, npu_cards=1)
        return RunnerCapacity(vcpus=None, npu_cards=None)

    def _collect_github_pr_metrics(
        self,
        repo: RepoEvalPolicy,
        ai_review_signals: list[str],
        errors: list[str],
    ) -> PullRequestMetrics:
        client = RepoEvalGitHubClient(token_env=repo.github.github_token_env)
        durations: list[float] = []
        workflow_run_evidence: list[str] = []
        cpu_core_minutes = 0.0
        npu_card_minutes = 0.0
        run_count = 0
        ai_review_evidence = list(ai_review_signals)
        seen_run_ids: set[int] = set()
        sampled_pull_count = 0
        markers = _ai_review_markers(repo)
        window_days = repo.github.pr_window_days
        collection_notes: list[str] = []
        workflow_error: str | None = None
        review_error: str | None = None

        if not getattr(client, "token", ""):
            collection_notes.append(
                "GitHub API 当前使用匿名访问，可能受到 rate limit 影响。"
            )

        try:
            for event in repo.github.workflow_events:
                runs = client.list_workflow_runs(
                    repo.name, event, self.cfg.recent_pr_limit
                )
                for run in runs:
                    updated_at = run.get("updated_at") or run.get("created_at")
                    if not _in_window(updated_at, window_days):
                        continue
                    run_id = int(run.get("id"))
                    if run_id in seen_run_ids:
                        continue
                    seen_run_ids.add(run_id)
                    run_count += 1
                    duration = _duration_seconds(
                        run.get("run_started_at") or run.get("created_at"),
                        run.get("updated_at"),
                    )
                    if duration is not None:
                        durations.append(duration)
                    workflow_run_evidence.append(
                        f"run:{run_id} {run.get('name', '')} {run.get('event', event)}"
                    )
                    jobs = client.list_workflow_jobs(repo.name, run_id)
                    for job in jobs:
                        labels = [str(x) for x in (job.get("labels") or [])]
                        cap = self._runner_capacity_for_job(repo, labels)
                        job_duration = _duration_seconds(
                            job.get("started_at"), job.get("completed_at")
                        )
                        if job_duration is None:
                            continue
                        if cap.vcpus is not None:
                            cpu_core_minutes += (job_duration / 60.0) * cap.vcpus
                        if cap.npu_cards is not None:
                            npu_card_minutes += (job_duration / 60.0) * cap.npu_cards
        except Exception as exc:
            workflow_error = f"failed to collect workflow runs: {exc}"
            errors.append(workflow_error)
            collection_notes.append("GitHub workflow 数据采集失败。")

        try:
            pulls = client.list_recent_pulls(repo.name, self.cfg.recent_review_pr_limit)
            for pull in pulls:
                updated_at = pull.get("updated_at") or pull.get("created_at")
                if not _in_window(updated_at, window_days):
                    continue
                sampled_pull_count += 1
                pull_number = int(pull["number"])
                reviews = client.list_reviews(repo.name, pull_number)
                for review in reviews:
                    author = _comment_author(review)
                    body = _comment_body(review)
                    if _looks_like_ai_review(author, body, markers):
                        signal = f"pr#{pull_number} review by {author}"
                        if signal not in ai_review_evidence:
                            ai_review_evidence.append(signal)
                issue_comments = client.list_issue_comments(repo.name, pull_number)
                for comment in issue_comments:
                    author = _comment_author(comment)
                    body = _comment_body(comment)
                    if _looks_like_ai_review(author, body, markers):
                        signal = f"pr#{pull_number} comment by {author}"
                        if signal not in ai_review_evidence:
                            ai_review_evidence.append(signal)
        except Exception as exc:
            review_error = f"failed to collect PR review signals: {exc}"
            errors.append(review_error)
            collection_notes.append("GitHub PR review/comment 数据采集失败。")

        now = datetime.now(timezone.utc)
        if run_count == 0 and workflow_error is None:
            collection_notes.append(
                f"最近 {window_days} 天内没有可用的 GitHub Actions workflow 样本。"
            )
        if sampled_pull_count == 0 and review_error is None:
            collection_notes.append(f"最近 {window_days} 天内没有可用的 PR 样本。")
        if durations:
            summary_note = f"collected from GitHub Actions and PR APIs within the last {window_days} days"
        else:
            summary_note = (
                "；".join(dict.fromkeys(note for note in collection_notes if note))
                or f"no recent GitHub PR activity found in the last {window_days} days"
            )
        return PullRequestMetrics(
            remote_platform="github",
            pr_window_days=window_days,
            window_start=(now - timedelta(days=window_days)).isoformat(),
            window_end=now.isoformat(),
            sampled_pull_count=sampled_pull_count,
            workflow_run_count=run_count,
            latest_duration_sec=durations[0] if durations else None,
            median_duration_sec=statistics.median(durations) if durations else None,
            average_duration_sec=(sum(durations) / len(durations))
            if durations
            else None,
            estimated_cpu_core_minutes=cpu_core_minutes if cpu_core_minutes else None,
            estimated_npu_card_minutes=npu_card_minutes if npu_card_minutes else None,
            ai_review_supported=bool(ai_review_evidence),
            ai_review_evidence=ai_review_evidence,
            workflow_run_evidence=workflow_run_evidence[:20],
            collection_note=summary_note,
        )

    def _collect_gitcode_pr_metrics(
        self,
        repo: RepoEvalPolicy,
        ai_review_signals: list[str],
        errors: list[str],
    ) -> PullRequestMetrics:
        client = RepoEvalGitCodeClient(token_env=repo.github.gitcode_token_env)
        window_days = repo.github.pr_window_days
        now = datetime.now(timezone.utc)
        if not client.token:
            return PullRequestMetrics(
                remote_platform="gitcode",
                pr_window_days=window_days,
                window_start=(now - timedelta(days=window_days)).isoformat(),
                window_end=now.isoformat(),
                ai_review_supported=bool(ai_review_signals),
                ai_review_evidence=list(ai_review_signals),
                collection_note=(
                    "GitCode 适配当前只支持 PR 评论/AI 检视信号采集，"
                    "PR workflow 时长与资源指标暂未接入；"
                    f"如需评论采集，请设置 {repo.github.gitcode_token_env}"
                ),
            )

        ai_review_evidence = list(ai_review_signals)
        sampled_pull_count = 0
        markers = _ai_review_markers(repo)
        try:
            pulls = client.list_recent_pulls(repo.name, self.cfg.recent_review_pr_limit)
            for pull in pulls:
                updated_at = pull.get("updated_at") or pull.get("created_at")
                if not _in_window(updated_at, window_days):
                    continue
                sampled_pull_count += 1
                pull_number = int(pull.get("number") or pull.get("iid") or 0)
                if not pull_number:
                    continue
                comments = client.list_pull_comments(repo.name, pull_number)
                for comment in comments:
                    author = _comment_author(comment)
                    body = _comment_body(comment)
                    if _looks_like_ai_review(author, body, markers):
                        signal = f"pr#{pull_number} comment by {author}"
                        if signal not in ai_review_evidence:
                            ai_review_evidence.append(signal)
        except Exception as exc:
            errors.append(f"failed to collect GitCode PR review signals: {exc}")

        return PullRequestMetrics(
            remote_platform="gitcode",
            pr_window_days=window_days,
            window_start=(now - timedelta(days=window_days)).isoformat(),
            window_end=now.isoformat(),
            sampled_pull_count=sampled_pull_count,
            ai_review_supported=bool(ai_review_evidence),
            ai_review_evidence=ai_review_evidence,
            collection_note=(
                f"collected GitCode PR comment signals within the last {window_days} days; "
                "workflow 时长与资源指标暂未接入"
                if sampled_pull_count
                else (
                    f"no recent GitCode PR activity found in the last {window_days} days; "
                    "workflow 时长与资源指标暂未接入"
                )
            ),
        )

    def _collect_pr_metrics(
        self,
        repo: RepoEvalPolicy,
        repo_path: Path,
        ai_review_signals: list[str],
        errors: list[str],
    ) -> PullRequestMetrics:
        origin_url = _git_remote_origin(repo_path)
        platform_probe = RepoEvalPolicy(
            name=repo.name,
            local_path=repo.local_path,
            clone_url=repo.clone_url or origin_url,
            local=repo.local,
            github=repo.github,
            ai=repo.ai,
        )
        remote_platform = _infer_remote_platform(platform_probe)
        if remote_platform == "gitcode":
            return self._collect_gitcode_pr_metrics(repo, ai_review_signals, errors)
        return self._collect_github_pr_metrics(repo, ai_review_signals, errors)
