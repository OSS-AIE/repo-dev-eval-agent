from __future__ import annotations

from pathlib import Path

import yaml

from .repo_eval_models import (
    AIEvalConfig,
    LocalEvalConfig,
    RemoteEvalConfig,
    RepoEvalAppConfig,
    RepoEvalPolicy,
    RunnerCapacity,
)


def load_repo_eval_config(path: str) -> RepoEvalAppConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    repos: list[RepoEvalPolicy] = []
    for item in raw.get("repos", []):
        local_raw = item.get("local", {}) or {}
        github_raw = item.get("github", {}) or {}
        ai_raw = item.get("ai", {}) or {}
        overrides = {
            label: RunnerCapacity(
                vcpus=details.get("vcpus"),
                npu_cards=details.get("npu_cards"),
            )
            for label, details in (
                github_raw.get("runner_capacity_overrides", {}) or {}
            ).items()
        }
        repos.append(
            RepoEvalPolicy(
                name=item["name"],
                local_path=item.get("local_path", ""),
                clone_url=item.get("clone_url", ""),
                local=LocalEvalConfig(
                    setup_command=local_raw.get("setup_command", ""),
                    command_prefix=local_raw.get("command_prefix", ""),
                    build_command=local_raw.get("build_command", ""),
                    incremental_build_command=local_raw.get(
                        "incremental_build_command", ""
                    ),
                    unit_test_command=local_raw.get("unit_test_command", ""),
                    code_check_command=local_raw.get("code_check_command", ""),
                    runner=local_raw.get("runner", "host"),
                    wsl_distro=local_raw.get("wsl_distro", ""),
                    refresh_local_repo=bool(local_raw.get("refresh_local_repo", True)),
                    documentation_refs=list(
                        local_raw.get("documentation_refs", []) or []
                    ),
                    timeout_sec=int(
                        local_raw.get(
                            "timeout_sec", raw.get("default_timeout_sec", 1800)
                        )
                    ),
                ),
                github=RemoteEvalConfig(
                    workflow_events=list(
                        github_raw.get("workflow_events", ["pull_request"])
                    ),
                    runner_capacity_overrides=overrides,
                    pr_window_days=int(github_raw.get("pr_window_days", 30)),
                    github_token_env=github_raw.get("github_token_env", "GITHUB_TOKEN"),
                    gitcode_token_env=github_raw.get(
                        "gitcode_token_env", "GITCODE_TOKEN"
                    ),
                    ai_review_author_markers=list(
                        github_raw.get("ai_review_author_markers", []) or []
                    ),
                ),
                ai=AIEvalConfig(
                    enabled=bool(ai_raw.get("enabled", False)),
                    provider=ai_raw.get("provider", ""),
                    command=ai_raw.get("command", ""),
                    command_template=ai_raw.get("command_template", ""),
                    model=ai_raw.get("model", ""),
                ),
            )
        )
    return RepoEvalAppConfig(
        workspace_root=raw.get("workspace_root", ".work/eval"),
        report_root=raw.get("report_root", "reports/eval"),
        recent_pr_limit=int(raw.get("recent_pr_limit", 10)),
        recent_review_pr_limit=int(raw.get("recent_review_pr_limit", 10)),
        default_timeout_sec=int(raw.get("default_timeout_sec", 1800)),
        enable_command_inference=bool(raw.get("enable_command_inference", True)),
        enable_local_commands=bool(raw.get("enable_local_commands", False)),
        repos=repos,
    )
