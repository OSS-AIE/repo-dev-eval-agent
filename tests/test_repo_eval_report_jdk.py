from __future__ import annotations

from oss_issue_fixer.repo_eval_models import (
    CommandExecutionResult,
    PullRequestMetrics,
    RepoEvaluationResult,
    StaticAnalysisResult,
)
from oss_issue_fixer.repo_eval_report import render_repo_eval_markdown


def test_render_repo_eval_markdown_classifies_jdk_version_mismatch():
    result = RepoEvaluationResult(
        repo="apache/logging-log4j2",
        local_path="D:\\vbox\\repos\\apache__logging-log4j2",
        static=StaticAnalysisResult(),
        incremental_build=CommandExecutionResult(
            status="failed",
            command="mvn -q -DskipTests package",
            duration_sec=1.4,
            stderr_excerpt=(
                "RequireJavaVersion failed. Detected JDK version 21.0.10 "
                "(JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64) is not in the "
                "allowed range [17,18)."
            ),
        ),
        code_check=CommandExecutionResult(status="not_configured"),
        unit_test=CommandExecutionResult(status="not_configured"),
        pr_metrics=PullRequestMetrics(),
    )

    report = render_repo_eval_markdown([result])

    assert "JDK" in report
