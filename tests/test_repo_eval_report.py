from __future__ import annotations

from oss_issue_fixer.repo_eval_models import (
    CommandExecutionResult,
    ContainerEnvironmentAssessment,
    ContainerRuntimeProbe,
    DocumentationAssessment,
    DocumentationCommand,
    DocumentationIssue,
    PullRequestMetrics,
    RepoEvaluationResult,
    StaticAnalysisResult,
)
from oss_issue_fixer.repo_eval_report import (
    render_repo_eval_html,
    render_repo_eval_markdown,
)


def _failing_result() -> RepoEvaluationResult:
    return RepoEvaluationResult(
        repo="Ascend/MindIE-SD",
        local_path="D:\\vbox\\repos\\MindIE-SD",
        static=StaticAnalysisResult(
            style_defined=True,
            style_evidence=[".editorconfig"],
            code_check_supported=True,
            check_tools=["pre-commit", "pytest"],
            rule_count_estimate=8,
            auto_fix_supported=True,
            auto_fix_evidence=["pre-commit:ruff-format"],
            inferred_build_command="bash build/build.sh",
            inferred_unit_test_command="bash tests/run_test.sh",
            inferred_code_check_command="pre-commit run -a",
            inference_evidence=[
                "build/build.sh detected",
                "remote docs: origin/master",
            ],
            container_environment=ContainerEnvironmentAssessment(
                defined=True,
                runnable_definition_present=False,
                preferred_strategy="docker_documented",
                reference_files=["docker/README.md"],
                note="docker is documented, but no runnable container definition was found",
                setup_blockers=[
                    "repository mentions Docker but does not provide a runnable Dockerfile"
                ],
                runtime=ContainerRuntimeProbe(
                    engine="docker",
                    cli_available=True,
                    daemon_available=True,
                    server_version="29.2.0",
                ),
            ),
            documentation=DocumentationAssessment(
                markdown_files_scanned=2,
                relevant_files=[
                    "docs/developer_guide.md",
                    "origin/master:docs/zh/developer_guide.md",
                ],
                commands=[
                    DocumentationCommand(
                        source_file="origin/master:docs/zh/developer_guide.md",
                        category="container",
                        command=(
                            "docker run -it --rm --privileged "
                            "mindie:2.2.RC1-800I-A2-py311-openeuler24.03-lts bash"
                        ),
                    ),
                    DocumentationCommand(
                        source_file="origin/master:docs/zh/developer_guide.md",
                        category="check",
                        command="pre-commit run -a",
                    ),
                ],
            ),
        ),
        incremental_build=CommandExecutionResult(
            status="failed",
            command="bash build/build.sh",
            duration_sec=0.06,
            stderr_excerpt="build/build.sh: line 12: $'\\r': command not found",
        ),
        code_check=CommandExecutionResult(
            status="failed",
            command="pre-commit run -a",
            duration_sec=0.12,
            stderr_excerpt="pre-commit: command not found",
        ),
        unit_test=CommandExecutionResult(
            status="failed",
            command="bash tests/run_test.sh",
            duration_sec=0.05,
            stderr_excerpt="tests/run_test.sh: line 4: $'\\r': command not found",
        ),
        pr_metrics=PullRequestMetrics(
            remote_platform="gitcode",
            pr_window_days=30,
            sampled_pull_count=1,
            ai_review_supported=True,
            ai_review_evidence=["pr#215 comment by ascend-robot"],
            collection_note="GitCode 适配当前只支持 PR 评论与 AI 检视信号采集，PR workflow 时长与资源指标暂未接入",
        ),
        documentation_issues=[
            DocumentationIssue(
                category="repository_script_issue",
                root_cause="repository",
                severity="high",
                summary="测试失败根因在仓库脚本内容或 CRLF/LF 行尾格式，不是 Markdown 描述不清",
                evidence=["tests/run_test.sh: line 4: $'\\r': command not found"],
                recommendation="修复脚本为 LF 行尾，并增加 CI 烟测。",
            ),
            DocumentationIssue(
                category="container_docs_not_self_contained",
                root_cause="documentation",
                severity="high",
                summary="Markdown 提到了容器路径，但仓库内没有可直接复现的容器定义",
                evidence=["docker/README.md"],
                recommendation="补充 Dockerfile 或 docker load / docker pull 的可执行入口。",
            ),
        ],
    )


def _successful_result() -> RepoEvaluationResult:
    return RepoEvaluationResult(
        repo="OSS-AIE/repo-dev-eval-agent",
        local_path="D:\\vbox\\repos\\repo_dev_eval_agent",
        static=StaticAnalysisResult(
            style_defined=True,
            style_evidence=["pyproject.toml:[tool.ruff]", ".pre-commit-config.yaml"],
            code_check_supported=True,
            check_tools=["pre-commit", "ruff", "pytest"],
            rule_count_estimate=12,
            auto_fix_supported=True,
            auto_fix_evidence=["ruff format", "pre-commit"],
            inferred_build_command="python -m build",
            inferred_unit_test_command="pytest tests -q",
            inferred_code_check_command="pre-commit run -a",
            inference_evidence=["pyproject.toml includes build backend"],
            documentation=DocumentationAssessment(
                markdown_files_scanned=1,
                relevant_files=["README.md"],
                commands=[
                    DocumentationCommand(
                        source_file="README.md",
                        category="build",
                        command="python -m build",
                    ),
                    DocumentationCommand(
                        source_file="README.md",
                        category="test",
                        command="pytest tests -q",
                    ),
                    DocumentationCommand(
                        source_file="README.md",
                        category="check",
                        command="pre-commit run -a",
                    ),
                ],
            ),
        ),
        incremental_build=CommandExecutionResult(
            status="ok",
            command="python -m build",
            duration_sec=6.37,
            returncode=0,
            stdout_excerpt="Successfully built wheel and sdist",
        ),
        code_check=CommandExecutionResult(
            status="ok",
            command="pre-commit run -a",
            duration_sec=4.12,
            returncode=0,
            stdout_excerpt="Passed",
        ),
        unit_test=CommandExecutionResult(
            status="ok",
            command="pytest tests -q",
            duration_sec=9.45,
            returncode=0,
            stdout_excerpt="36 passed",
        ),
        pr_metrics=PullRequestMetrics(
            remote_platform="github",
            pr_window_days=30,
            sampled_pull_count=8,
            workflow_run_count=16,
            latest_duration_sec=411.0,
            median_duration_sec=355.0,
            average_duration_sec=368.5,
            estimated_cpu_core_minutes=42.5,
            ai_review_supported=True,
            ai_review_evidence=["pr#2 comment by github-actions[bot]"],
            workflow_run_evidence=[
                "run:1 CI pull_request",
                "run:2 CodeQL pull_request",
            ],
            collection_note="collected from GitHub Actions and PR APIs within the last 30 days",
        ),
    )


def test_render_repo_eval_markdown_includes_root_causes_and_success_evidence():
    report = render_repo_eval_markdown([_failing_result(), _successful_result()])

    assert "开源代码仓开发体验评估报告" in report
    assert "失败根因分析" in report
    assert "成功证据链" in report
    assert "无可运行镜像或容器定义" in report
    assert "仓库脚本问题" in report
    assert "PR 流水线指标暂未接入" in report
    assert "命令来源: 仓库结构推断" in report
    assert "返回码: 0" in report
    assert "run:1 CI pull_request" in report


def test_render_repo_eval_html_contains_cards_tabs_and_evidence_sections():
    html = render_repo_eval_html([_failing_result(), _successful_result()])

    assert '<html lang="zh-CN">' in html
    assert "开源代码仓开发体验评估报告" in html
    assert "仓库汇总" in html
    assert "repo-tab active" in html
    assert "showRepoTab" in html
    assert "成功证据链" in html
    assert "失败根因分析" in html
    assert "镜像环境下载失败" not in html
    assert "无可运行镜像或容器定义" in html
    assert "run:2 CodeQL pull_request" in html
