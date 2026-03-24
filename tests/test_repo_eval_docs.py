from __future__ import annotations

from oss_issue_fixer.repo_eval_docs import analyze_documentation_quality
from oss_issue_fixer.repo_eval_models import (
    CommandExecutionResult,
    DocumentationAssessment,
    DocumentationCommand,
    PullRequestMetrics,
    RepoEvaluationResult,
    StaticAnalysisResult,
)


def test_analyze_documentation_quality_flags_missing_code_check_docs():
    result = RepoEvaluationResult(
        repo="example/project",
        local_path="D:\\vbox\\repos\\example",
        static=StaticAnalysisResult(
            code_check_supported=True,
            inferred_build_command="python setup.py bdist_wheel",
            inferred_unit_test_command="pytest -q",
            inferred_code_check_command="pre-commit run -a",
            check_tools=[".pre-commit-config.yaml"],
            documentation=DocumentationAssessment(
                markdown_files_scanned=1,
                relevant_files=["README.md"],
                commands=[
                    DocumentationCommand(
                        source_file="README.md",
                        category="build",
                        command="python setup.py bdist_wheel",
                    )
                ],
            ),
        ),
        incremental_build=CommandExecutionResult(
            status="ok",
            command="python setup.py bdist_wheel",
        ),
        unit_test=CommandExecutionResult(status="ok", command="pytest -q"),
        code_check=CommandExecutionResult(status="not_configured"),
        pr_metrics=PullRequestMetrics(),
    )

    issues = analyze_documentation_quality(result)

    assert any(issue.category == "missing_code_check_docs" for issue in issues)
    assert any(issue.category == "missing_test_command_docs" for issue in issues)


def test_analyze_documentation_quality_classifies_dependency_and_script_failures():
    result = RepoEvaluationResult(
        repo="Ascend/MindIE-SD",
        local_path="D:\\vbox\\repos\\MindIE-SD",
        static=StaticAnalysisResult(
            documentation=DocumentationAssessment(
                markdown_files_scanned=1,
                relevant_files=["docs/developer_guide.md"],
                commands=[
                    DocumentationCommand(
                        source_file="docs/developer_guide.md",
                        category="test",
                        command="pytest tests/",
                    )
                ],
            ),
        ),
        incremental_build=CommandExecutionResult(
            status="failed",
            command="python setup.py bdist_wheel",
            stderr_excerpt=(
                "Because torch==2.1.0 has no wheels with a matching Python ABI tag "
                "(e.g., cp312)"
            ),
        ),
        unit_test=CommandExecutionResult(
            status="failed",
            command="bash tests/run_test.sh",
            stderr_excerpt="tests/run_test.sh: line 4: $'\\r': command not found",
        ),
        code_check=CommandExecutionResult(status="not_configured"),
        pr_metrics=PullRequestMetrics(),
    )

    issues = analyze_documentation_quality(result)

    assert any(issue.category == "missing_version_prerequisite" for issue in issues)
    assert any(issue.category == "repository_script_issue" for issue in issues)
