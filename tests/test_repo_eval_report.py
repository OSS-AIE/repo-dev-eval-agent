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


def _sample_result() -> RepoEvaluationResult:
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
            collection_note="GitCode AI review detection requires a private token",
        ),
        documentation_issues=[
            DocumentationIssue(
                category="repository_script_issue",
                root_cause="repository",
                severity="high",
                summary="测试失败根因在仓库脚本内容或 CRLF/LF 行尾格式，不是 Markdown 描述不清",
                evidence=["tests/run_test.sh: line 4: $'\\r': command not found"],
                recommendation="修复脚本为 LF 行尾，并增加 CI 烟测。",
            )
        ],
    )


def test_render_repo_eval_markdown_includes_failure_excerpts_and_doc_issues():
    report = render_repo_eval_markdown([_sample_result()])

    assert "开源代码仓开发体验评估报告" in report
    assert "增量构建失败摘要" in report
    assert "代码检测失败摘要" in report
    assert "UT 失败摘要" in report
    assert "docker_documented" in report
    assert "文档中的代码检测命令" in report
    assert "Markdown 改进建议总览" in report
    assert "repository_script_issue" in report
    assert "修复脚本为 LF 行尾" in report
    assert "N/A" in report


def test_render_repo_eval_html_contains_summary_and_tabs():
    html = render_repo_eval_html([_sample_result(), _sample_result()])

    assert '<html lang="zh-CN">' in html
    assert "开源代码仓开发体验评估报告" in html
    assert "仓库汇总" in html
    assert "repo-tab active" in html
    assert "showRepoTab" in html
    assert "Ascend/MindIE-SD" in html
    assert "Markdown 改进建议总览" in html
    assert "pr#215 comment by ascend-robot" in html
