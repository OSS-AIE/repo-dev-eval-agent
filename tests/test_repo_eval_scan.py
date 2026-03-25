from __future__ import annotations

import subprocess
from pathlib import Path

from oss_issue_fixer.repo_eval_models import ContainerRuntimeProbe
from oss_issue_fixer.repo_eval_scan import infer_local_commands, scan_repository


def test_scan_repository_detects_style_checks_and_autofix(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    (tmp_path / ".editorconfig").write_text("root = true\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.ruff.lint]
select = ["E", "F", "I"]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / ".pre-commit-config.yaml").write_text(
        """
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
      - id: ruff-format
""".strip(),
        encoding="utf-8",
    )
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "pr.yml").write_text(
        """
name: PR
on:
  pull_request:
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: ruff check .
      - run: ruff format --check .
      - uses: coderabbitai/ai-pr-reviewer@v1
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()

    result = scan_repository(tmp_path)
    infer_local_commands(tmp_path, result)

    assert result.style_defined is True
    assert result.code_check_supported is True
    assert result.auto_fix_supported is True
    assert result.rule_count_estimate >= 5
    assert any("coderabbit" in item for item in result.ai_review_signals)
    assert result.inferred_code_check_command == "pre-commit run -a"
    assert result.inferred_unit_test_command == "pytest -q"


def test_scan_repository_detects_shell_driven_repo_patterns(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    (tmp_path / "requirements.txt").write_text(
        "torch\npre-commit==3.8.0\npytest\n",
        encoding="utf-8",
    )
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "build.sh").write_text("#!/bin/bash\nmake all\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / ".coveragerc").write_text("[run]\nbranch = True\n", encoding="utf-8")
    (tests_dir / "run_UT_test.sh").write_text(
        "#!/bin/bash\npython -m coverage run -m pytest tests/UT\n",
        encoding="utf-8",
    )

    result = scan_repository(tmp_path)
    infer_local_commands(tmp_path, result)

    assert result.code_check_supported is True
    assert any("requirements.txt:pre-commit" == item for item in result.check_tools)
    assert any("test-script" in item for item in result.check_tools)
    assert result.inferred_build_command == "bash build/build.sh"
    assert result.inferred_unit_test_command == "bash tests/run_UT_test.sh"


def test_scan_repository_extracts_commands_from_markdown_docs(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "developer_guide.md").write_text(
        """
# Developer Guide

```bash
python -m venv .venv
pip install -r requirements.txt
python setup.py bdist_wheel
pre-commit run -a
pytest tests/
docker pull example/project:latest
```
""".strip(),
        encoding="utf-8",
    )

    result = scan_repository(tmp_path)
    infer_local_commands(tmp_path, result)

    assert result.documentation.markdown_files_scanned == 1
    assert "docs/developer_guide.md" in result.documentation.relevant_files
    assert any(item.category == "build" for item in result.documentation.commands)
    assert any(item.category == "test" for item in result.documentation.commands)
    assert any(item.category == "check" for item in result.documentation.commands)
    assert any(item.category == "container" for item in result.documentation.commands)
    assert result.inferred_build_command == "python setup.py bdist_wheel"
    assert result.inferred_unit_test_command == "pytest tests/"
    assert result.inferred_code_check_command == "pre-commit run -a"


def test_scan_repository_can_merge_markdown_from_git_ref(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    subprocess.run("git init", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        'git config user.email "tester@example.com"',
        cwd=tmp_path,
        shell=True,
        check=True,
    )
    subprocess.run(
        'git config user.name "Test User"',
        cwd=tmp_path,
        shell=True,
        check=True,
    )
    docs_dir = tmp_path / "docs" / "zh"
    docs_dir.mkdir(parents=True)
    remote_doc = docs_dir / "developer_guide.md"
    remote_doc.write_text(
        """
# 开发者指南

```bash
docker run --rm example/image:latest bash
python setup.py bdist_wheel
bash tests/run_test.sh
```
""".strip(),
        encoding="utf-8",
    )
    subprocess.run("git add .", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        'git commit -m "add remote docs"',
        cwd=tmp_path,
        shell=True,
        check=True,
    )
    remote_doc.unlink()

    result = scan_repository(tmp_path, documentation_refs=["HEAD"])
    infer_local_commands(tmp_path, result)

    assert result.documentation.markdown_files_scanned == 1
    assert "HEAD:docs/zh/developer_guide.md" in result.documentation.relevant_files
    assert any(item.category == "container" for item in result.documentation.commands)
    assert result.inferred_build_command == "python setup.py bdist_wheel"
    assert result.inferred_unit_test_command == "bash tests/run_test.sh"


def test_scan_repository_follows_external_vllm_doc_skills(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    (tmp_path / "README.md").write_text(
        (
            "Please check out [Contributing to vLLM]"
            "(https://docs.vllm.ai/en/latest/contributing/index.html)"
            " for how to get involved.\n"
        ),
        encoding="utf-8",
    )

    class _Resp:
        def __init__(self, text: str) -> None:
            self.text = text
            self.headers = {"Content-Type": "text/html; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan.requests.get",
        lambda url, timeout=30: _Resp(
            """
            <html><body>
            <h1>Contributing to vLLM</h1>
            <pre><code>uv venv --python 3.12 --seed
VLLM_USE_PRECOMPILED=1 uv pip install -U -e . --torch-backend=auto
uv pip install pytest pytest-asyncio
pre-commit run -a
pytest tests/
            </code></pre>
            </body></html>
            """
        ),
    )

    result = scan_repository(tmp_path, repo_name="vllm-project/vllm")
    infer_local_commands(tmp_path, result)

    assert any(
        item.source_file == "https://docs.vllm.ai/en/latest/contributing/index.html"
        and item.category == "build"
        for item in result.documentation.commands
    )
    assert any("community doc skill" in note for note in result.documentation.notes)
    assert result.inferred_build_command.startswith("VLLM_USE_PRECOMPILED=1 uv pip")
    assert result.inferred_unit_test_command == "pytest tests/"
    assert result.inferred_code_check_command == "pre-commit run -a"


def test_scan_repository_maps_gitcode_blob_skill_to_git_ref(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    subprocess.run("git init", cwd=tmp_path, shell=True, check=True)
    subprocess.run(
        'git config user.email "tester@example.com"',
        cwd=tmp_path,
        shell=True,
        check=True,
    )
    subprocess.run(
        'git config user.name "Test User"',
        cwd=tmp_path,
        shell=True,
        check=True,
    )
    (tmp_path / "README.md").write_text(
        (
            "[开发指南]"
            "(https://gitcode.com/Ascend/MindIE-SD/blob/master/docs/zh/developer_guide.md)\n"
        ),
        encoding="utf-8",
    )
    zh_dir = tmp_path / "docs" / "zh"
    zh_dir.mkdir(parents=True)
    (zh_dir / "developer_guide.md").write_text(
        """
        ```bash
        docker run --rm mindie:2.2.RC1 bash
        python setup.py bdist_wheel
        bash tests/run_UT_test.sh
        ```
        """.strip(),
        encoding="utf-8",
    )
    subprocess.run("git add .", cwd=tmp_path, shell=True, check=True)
    subprocess.run('git commit -m "add zh guide"', cwd=tmp_path, shell=True, check=True)

    result = scan_repository(tmp_path, repo_name="Ascend/MindIE-SD")
    infer_local_commands(tmp_path, result)

    assert (
        "master:docs/zh/developer_guide.md" in result.documentation.relevant_files
        or (
            "origin/master:docs/zh/developer_guide.md"
            in result.documentation.relevant_files
        )
    )
    assert any(item.category == "container" for item in result.documentation.commands)
    assert result.inferred_build_command == "python setup.py bdist_wheel"


def test_scan_repository_detects_runnable_docker_environment(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
            nvidia_runtime_available=True,
            evidence=["docker cli available", "docker daemon 29.2.0"],
        ),
    )
    docker_dir = tmp_path / "docker"
    docker_dir.mkdir()
    (docker_dir / "Dockerfile").write_text(
        """
ARG BASE_IMAGE=nvidia/cuda:12.4.1-devel-ubuntu22.04
FROM ${BASE_IMAGE} AS base
FROM base AS final
RUN echo ok
""".strip(),
        encoding="utf-8",
    )

    result = scan_repository(tmp_path)
    infer_local_commands(tmp_path, result)

    assert result.container_environment.defined is True
    assert result.container_environment.runnable_definition_present is True
    assert result.container_environment.setup_supported_locally is True
    assert result.container_environment.preferred_strategy == "docker_build"
    assert "docker/Dockerfile" in result.container_environment.dockerfiles
    assert any(
        "nvidia/cuda:12.4.1-devel-ubuntu22.04" in image
        for image in result.container_environment.base_images
    )
    assert "base" not in result.container_environment.base_images
    assert result.container_environment.requires_gpu is True
    assert "container strategy: docker_build" in result.inference_evidence


def test_scan_repository_reports_documented_only_docker_environment(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    docker_dir = tmp_path / "docker"
    docker_dir.mkdir()
    (docker_dir / "README.md").write_text(
        "# Docker\n\nBuild docker image.\n",
        encoding="utf-8",
    )

    result = scan_repository(tmp_path)
    infer_local_commands(tmp_path, result)

    assert result.container_environment.defined is True
    assert result.container_environment.runnable_definition_present is False
    assert result.container_environment.setup_supported_locally is False
    assert result.container_environment.preferred_strategy == "docker_documented"
    assert "docker/README.md" in result.container_environment.reference_files
    assert "no runnable container definition" in result.container_environment.note


def test_scan_repository_ignores_directories_named_dockerfile(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    docker_dir = tmp_path / "docs" / "contributing" / "Dockerfile"
    docker_dir.mkdir(parents=True)
    (docker_dir / "dockerfile.md").write_text(
        "not a docker build file\n", encoding="utf-8"
    )

    result = scan_repository(tmp_path)

    assert result.container_environment.defined is False
    assert result.container_environment.dockerfiles == []


def test_scan_repository_ignores_generated_workdirs_and_reports(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setattr(
        "oss_issue_fixer.repo_eval_scan._probe_container_runtime",
        lambda: ContainerRuntimeProbe(
            engine="docker",
            cli_available=True,
            daemon_available=True,
            server_version="29.2.0",
        ),
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "developer_guide.md").write_text(
        "```bash\npytest tests/\n```",
        encoding="utf-8",
    )
    work_dir = tmp_path / ".work" / "nested"
    work_dir.mkdir(parents=True)
    (work_dir / "README.md").write_text(
        "```bash\ndocker run ignored/image:latest\n```",
        encoding="utf-8",
    )
    reports_dir = tmp_path / "reports" / "samples"
    reports_dir.mkdir(parents=True)
    (reports_dir / "sample.md").write_text(
        "```bash\npre-commit run -a\n```",
        encoding="utf-8",
    )

    result = scan_repository(tmp_path)

    assert result.documentation.markdown_files_scanned == 1
    assert result.documentation.relevant_files == ["docs/developer_guide.md"]
