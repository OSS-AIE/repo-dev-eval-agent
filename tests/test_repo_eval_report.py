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
from oss_issue_fixer.repo_eval_report import render_repo_eval_markdown


def test_render_repo_eval_markdown_includes_failure_excerpts_and_doc_issues():
    result = RepoEvaluationResult(
        repo="Ascend/MindIE-SD",
        local_path="D:\\vbox\\repos\\MindIE-SD",
        static=StaticAnalysisResult(
            code_check_supported=True,
            inferred_build_command="bash build/build.sh",
            inferred_unit_test_command="bash tests/run_UT_test.sh",
            inferred_code_check_command="pre-commit run -a",
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
                relevant_files=["docs/developer_guide.md", "docker/README.md"],
                commands=[
                    DocumentationCommand(
                        source_file="docs/developer_guide.md",
                        category="check",
                        command="pre-commit run -a",
                    )
                ],
            ),
        ),
        incremental_build=CommandExecutionResult(
            status="failed",
            command="bash build/build.sh",
            stderr_excerpt="build/build.sh: line 12: $'\\r': command not found",
        ),
        code_check=CommandExecutionResult(
            status="failed",
            command="pre-commit run -a",
            stderr_excerpt="pre-commit: command not found",
        ),
        unit_test=CommandExecutionResult(
            status="failed",
            command="bash tests/run_UT_test.sh",
            stderr_excerpt="tests/run_UT_test.sh: syntax error: unexpected end of file",
        ),
        pr_metrics=PullRequestMetrics(
            remote_platform="gitcode",
            pr_window_days=30,
            collection_note="GitCode AI review detection requires a private token",
        ),
        documentation_issues=[
            DocumentationIssue(
                category="repository_script_issue",
                root_cause="repository",
                severity="high",
                summary="测试失败根因是仓库脚本内容或行尾格式问题，不是 Markdown 描述问题",
                evidence=["tests/run_UT_test.sh: syntax error: unexpected end of file"],
                recommendation="修复 shell 脚本行尾为 LF，并增加 CI 烟测。",
            )
        ],
    )

    report = render_repo_eval_markdown([result])

    assert "增量构建失败摘要" in report
    assert "代码检测失败摘要" in report
    assert "UT 失败摘要" in report
    assert "docker_documented" in report
    assert "文档中的代码检测命令" in report
    assert "Markdown 文档改进建议总览" in report
    assert "repository_script_issue" in report
    assert "修复 shell 脚本行尾为 LF" in report
