from __future__ import annotations

from .repo_eval_models import (
    CommandExecutionResult,
    DocumentationCommand,
    DocumentationIssue,
    RepoEvaluationResult,
)


def _doc_commands(
    result: RepoEvaluationResult,
    category: str,
) -> list[DocumentationCommand]:
    return [
        item
        for item in result.static.documentation.commands
        if item.category == category
    ]


def _append_issue(
    issues: list[DocumentationIssue],
    *,
    category: str,
    root_cause: str,
    severity: str,
    summary: str,
    evidence: list[str],
    recommendation: str,
) -> None:
    key = (category, root_cause, summary)
    for item in issues:
        if (item.category, item.root_cause, item.summary) == key:
            return
    issues.append(
        DocumentationIssue(
            category=category,
            root_cause=root_cause,
            severity=severity,
            summary=summary,
            evidence=[entry for entry in evidence if entry][:6],
            recommendation=recommendation,
        )
    )


def _failure_text(result: CommandExecutionResult) -> str:
    return " ".join(
        part.strip()
        for part in (result.stderr_excerpt, result.stdout_excerpt)
        if part.strip()
    ).lower()


def _classify_command_failure(
    issues: list[DocumentationIssue],
    area: str,
    command_result: CommandExecutionResult,
    documented: list[DocumentationCommand],
) -> None:
    if command_result.status not in {"failed", "timeout", "error"}:
        return

    text = _failure_text(command_result)
    evidence = [
        f"{area} command: {command_result.command or 'N/A'}",
        f"{area} status: {command_result.status}",
        f"{area} failure: {(command_result.stderr_excerpt or command_result.stdout_excerpt)[:240]}",
    ]
    if documented:
        evidence.append(
            "documented commands: "
            + "; ".join(f"{item.source_file}: {item.command}" for item in documented[:3])
        )

    if any(token in text for token in ("ssl:", "couldn't connect", "connection timed out", "unexpected eof")):
        _append_issue(
            issues,
            category="environment_network_blocker",
            root_cause="environment",
            severity="medium",
            summary=f"{area} 阶段受到网络或镜像源波动影响",
            evidence=evidence,
            recommendation="在文档中补充代理/镜像源/重试建议，并在 CI 中缓存依赖与 hook 环境。",
        )
        return

    if any(token in text for token in ("libcuda.so", "failed to infer device type", "nvidia-smi", "cuda")):
        _append_issue(
            issues,
            category="missing_environment_prerequisite",
            root_cause="environment",
            severity="high",
            summary=f"{area} 依赖 GPU/CUDA 运行时，但当前环境不满足",
            evidence=evidence,
            recommendation="在文档开头显式写明 GPU、CUDA 驱动和容器 runtime 前置条件，并给出 CPU 或 mock 路径（如果支持）。",
        )
        return

    if any(token in text for token in ("cp312", "cp311", "requires-python", "abi tag", "unsatisfiable", "no matching distribution")):
        _append_issue(
            issues,
            category="missing_version_prerequisite",
            root_cause="documentation",
            severity="high",
            summary=f"{area} 文档缺少明确的 Python/依赖版本前置条件",
            evidence=evidence,
            recommendation="把支持的 Python 版本、关键依赖版本和不兼容组合写进安装/构建章节，并在命令示例旁直接标注。",
        )
        return

    if any(token in text for token in ("module not founderror", "no module named")):
        _append_issue(
            issues,
            category="missing_dependency_step",
            root_cause="documentation",
            severity="high",
            summary=f"{area} 示例命令缺少必要依赖准备步骤",
            evidence=evidence,
            recommendation="补全测试/检测前的依赖安装步骤，并确保文档里的示例命令能在新环境直接跑通。",
        )
        return

    if any(token in text for token in ("$'\\r'", "unexpected end of file", "syntax error near unexpected token")):
        _append_issue(
            issues,
            category="repository_script_issue",
            root_cause="repository",
            severity="high",
            summary=f"{area} 失败根因是仓库脚本内容或行尾格式问题，不是 Markdown 描述问题",
            evidence=evidence,
            recommendation="修复脚本行尾为 LF，并通过 `.gitattributes` 固化 shell 脚本的文本格式。",
        )
        return

    if "command not found" in text and documented:
        _append_issue(
            issues,
            category="missing_tooling_prerequisite",
            root_cause="documentation",
            severity="medium",
            summary=f"{area} 文档给了命令，但缺少工具安装前置说明",
            evidence=evidence,
            recommendation="在命令前补充依赖工具安装步骤，例如 `pre-commit`、`uv`、`docker`、`pytest` 等。",
        )
        return

    _append_issue(
        issues,
        category="execution_failure_needs_manual_triage",
        root_cause="mixed",
        severity="medium",
        summary=f"{area} 命令执行失败，需要进一步区分是文档漂移还是仓库行为变化",
        evidence=evidence,
        recommendation="复核文档示例、依赖锁定和仓库脚本是否一致，并为该命令补一个 CI 烟测。",
    )


def analyze_documentation_quality(
    result: RepoEvaluationResult,
) -> list[DocumentationIssue]:
    issues: list[DocumentationIssue] = []
    docs = result.static.documentation
    build_docs = _doc_commands(result, "build")
    test_docs = _doc_commands(result, "test")
    check_docs = _doc_commands(result, "check")
    container_docs = _doc_commands(result, "container")

    if result.static.inferred_build_command and not build_docs:
        _append_issue(
            issues,
            category="missing_build_command_docs",
            root_cause="documentation",
            severity="medium",
            summary="仓库具备构建路径，但 Markdown 未给出可直接执行的构建命令",
            evidence=[f"inferred build command: {result.static.inferred_build_command}"],
            recommendation="在开发者文档中补充最小可运行的本地构建命令，并注明工作目录与前置依赖。",
        )

    if result.static.inferred_unit_test_command and not test_docs:
        _append_issue(
            issues,
            category="missing_test_command_docs",
            root_cause="documentation",
            severity="medium",
            summary="仓库具备测试路径，但 Markdown 未给出可直接执行的测试命令",
            evidence=[f"inferred test command: {result.static.inferred_unit_test_command}"],
            recommendation="在贡献或开发文档中补充最小 UT 命令，以及首次执行前需要安装的依赖集合。",
        )

    if result.static.code_check_supported and not check_docs:
        _append_issue(
            issues,
            category="missing_code_check_docs",
            root_cause="documentation",
            severity="medium",
            summary="仓库支持代码检测，但 Markdown 未给出 lint / pre-commit 执行说明",
            evidence=result.static.check_tools[:4],
            recommendation="补充代码检测章节，至少说明 lint 命令、自动修复命令和常见失败排查路径。",
        )

    container = result.static.container_environment
    if container_docs and not container.runnable_definition_present:
        _append_issue(
            issues,
            category="container_docs_not_self_contained",
            root_cause="documentation",
            severity="high",
            summary="Markdown 提到了容器路径，但仓库内没有可直接复现的容器定义",
            evidence=container.reference_files[:4] + container.setup_blockers[:2],
            recommendation="补充可直接执行的 `docker pull`/`docker load`/`docker build` 命令，或在仓库内提供 Dockerfile/compose/devcontainer。",
        )

    if any("login" in cmd.command.lower() or "download" in cmd.command.lower() for cmd in container_docs):
        _append_issue(
            issues,
            category="external_manual_dependency",
            root_cause="documentation",
            severity="medium",
            summary="容器准备依赖外部站点登录或手工下载，难以自动化复现",
            evidence=[f"{item.source_file}: {item.command}" for item in container_docs[:3]],
            recommendation="增加公开可访问的镜像拉取方式，或明确说明下载入口、鉴权方式和离线导入步骤。",
        )

    _classify_command_failure(issues, "构建", result.incremental_build, build_docs)
    _classify_command_failure(issues, "测试", result.unit_test, test_docs)
    _classify_command_failure(issues, "代码检测", result.code_check, check_docs)

    return issues
