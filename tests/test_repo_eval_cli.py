from __future__ import annotations

import subprocess
from pathlib import Path

from openpyxl import Workbook

from oss_issue_fixer.cli import _load_repo_inputs, _policy_from_repo_input
from oss_issue_fixer.repo_eval_models import AIEvalConfig, RemoteEvalConfig


def test_policy_from_repo_input_supports_github_url():
    policy = _policy_from_repo_input(
        "https://github.com/vllm-project/vllm",
        local_runner="wsl",
        local_wsl_distro="Ubuntu",
        local_wsl_workspace_root="~/.cache/repo-dev-eval/repos",
        remote_cfg=RemoteEvalConfig(pr_window_days=14),
        ai_cfg=AIEvalConfig(enabled=True, provider="codex"),
    )

    assert policy.name == "vllm-project/vllm"
    assert policy.clone_url == "https://github.com/vllm-project/vllm.git"
    assert policy.local.runner == "wsl"
    assert policy.local.wsl_distro == "Ubuntu"
    assert policy.local.wsl_workspace_root == "~/.cache/repo-dev-eval/repos"
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
        local_wsl_workspace_root="",
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
        local_wsl_workspace_root="",
        remote_cfg=RemoteEvalConfig(),
        ai_cfg=AIEvalConfig(),
    )

    assert policy.name == "vllm-project/vllm"
    assert policy.clone_url == "git@github.com:vllm-project/vllm.git"


def test_policy_from_repo_input_prefers_remote_matching_local_repo_name(
    tmp_path: Path,
):
    repo_dir = tmp_path / "repo_dev_eval_agent"
    repo_dir.mkdir()
    subprocess.run("git init", cwd=repo_dir, shell=True, check=True)
    subprocess.run(
        "git remote add origin https://github.com/robellliu-dev/oss-issue-fixer-agent.git",
        cwd=repo_dir,
        shell=True,
        check=True,
    )
    subprocess.run(
        "git remote add ossaie https://github.com/OSS-AIE/repo-dev-eval-agent.git",
        cwd=repo_dir,
        shell=True,
        check=True,
    )

    policy = _policy_from_repo_input(
        str(repo_dir),
        local_runner="host",
        local_wsl_distro="",
        local_wsl_workspace_root="",
        remote_cfg=RemoteEvalConfig(),
        ai_cfg=AIEvalConfig(),
    )

    assert policy.name == "OSS-AIE/repo-dev-eval-agent"
    assert policy.clone_url == "https://github.com/OSS-AIE/repo-dev-eval-agent.git"


def test_load_repo_inputs_merges_cli_and_xlsx_inputs(tmp_path: Path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "repos"
    sheet.append(["组织名", "项目名", "仓库名", "仓库链接"])
    sheet.append(
        ["Ascend", "MindIE", "MindIE-SD", "https://gitcode.com/Ascend/MindIE-SD.git"]
    )
    sheet.append(["vLLM", "vLLM", "vllm", "https://github.com/vllm-project/vllm.git"])
    xlsx_path = tmp_path / "repos.xlsx"
    workbook.save(xlsx_path)

    values = _load_repo_inputs(
        ["https://github.com/vllm-project/vllm.git"],
        repo_xlsx=str(xlsx_path),
        repo_sheet="repos",
    )

    assert values == [
        "https://github.com/vllm-project/vllm.git",
        "https://gitcode.com/Ascend/MindIE-SD.git",
    ]


def test_load_repo_inputs_supports_offset_and_limit(tmp_path: Path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["仓库链接"])
    sheet.append(["https://gitcode.com/Ascend/MindIE-SD.git"])
    sheet.append(["https://github.com/vllm-project/vllm.git"])
    sheet.append(["https://github.com/sgl-project/sglang.git"])
    xlsx_path = tmp_path / "repos.xlsx"
    workbook.save(xlsx_path)

    values = _load_repo_inputs(
        [],
        repo_xlsx=str(xlsx_path),
        repo_limit=1,
        repo_offset=1,
    )

    assert values == ["https://github.com/vllm-project/vllm.git"]
