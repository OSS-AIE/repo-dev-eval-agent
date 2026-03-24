from __future__ import annotations

import subprocess
from pathlib import Path

from oss_issue_fixer.cli import _policy_from_repo_input
from oss_issue_fixer.repo_eval_models import AIEvalConfig, RemoteEvalConfig


def test_policy_from_repo_input_supports_github_url():
    policy = _policy_from_repo_input(
        "https://github.com/vllm-project/vllm",
        local_runner="wsl",
        local_wsl_distro="Ubuntu",
        remote_cfg=RemoteEvalConfig(pr_window_days=14),
        ai_cfg=AIEvalConfig(enabled=True, provider="codex"),
    )

    assert policy.name == "vllm-project/vllm"
    assert policy.clone_url == "https://github.com/vllm-project/vllm.git"
    assert policy.local.runner == "wsl"
    assert policy.local.wsl_distro == "Ubuntu"
    assert policy.github.pr_window_days == 14
    assert policy.ai.provider == "codex"


def test_policy_from_repo_input_supports_local_path_with_remote(tmp_path: Path):
    subprocess.run("git init", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        "git remote add origin https://gitcode.com/Ascend/MindIE-SD.git",
        cwd=tmp_path,
        shell=True,
        check=True,
    )

    policy = _policy_from_repo_input(
        str(tmp_path),
        local_runner="host",
        local_wsl_distro="",
        remote_cfg=RemoteEvalConfig(),
        ai_cfg=AIEvalConfig(),
    )

    assert policy.name == "Ascend/MindIE-SD"
    assert policy.clone_url == "https://gitcode.com/Ascend/MindIE-SD.git"
    assert policy.local_path == str(tmp_path.resolve())


def test_policy_from_repo_input_supports_local_path_with_ssh_remote(tmp_path: Path):
    subprocess.run("git init", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        "git remote add origin git@github.com:vllm-project/vllm.git",
        cwd=tmp_path,
        shell=True,
        check=True,
    )

    policy = _policy_from_repo_input(
        str(tmp_path),
        local_runner="host",
        local_wsl_distro="",
        remote_cfg=RemoteEvalConfig(),
        ai_cfg=AIEvalConfig(),
    )

    assert policy.name == "vllm-project/vllm"
    assert policy.clone_url == "git@github.com:vllm-project/vllm.git"
