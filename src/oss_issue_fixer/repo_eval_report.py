from __future__ import annotations

from collections import Counter

from .repo_eval_models import CommandExecutionResult, RepoEvaluationResult


def _bool_text(value: bool) -> str:
    return "是" if value else "否"


def _duration_text(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}s"


def _metric_duration_text(result: CommandExecutionResult) -> str:
    if result.status != "ok":
        return "N/A"
    return _duration_text(result.duration_sec)


def _resource_text(item: RepoEvaluationResult) -> str:
    cpu = item.pr_metrics.actual_cpu_seconds
    if cpu is None and item.pr_metrics.estimated_cpu_core_minutes is not None:
        cpu_text = f"估算 {item.pr_metrics.estimated_cpu_core_minutes:.2f} core-min"
    elif cpu is not None:
        cpu_text = f"{cpu:.2f} cpu-sec"
    else:
        cpu_text = "N/A"

    npu = item.pr_metrics.actual_npu_seconds
    if npu is None and item.pr_metrics.estimated_npu_card_minutes is not None:
        npu_text = f"估算 {item.pr_metrics.estimated_npu_card_minutes:.2f} card-min"
    elif npu is not None:
        npu_text = f"{npu:.2f} npu-sec"
    else:
        npu_text = "N/A"
    return f"CPU: {cpu_text}; NPU: {npu_text}"


def _join(values: list[str], limit: int = 8) -> str:
    return "<br>".join(values[:limit]) if values else "N/A"


def _command_failure_text(result: CommandExecutionResult) -> str:
    if result.status not in {"failed", "timeout", "error"}:
        return ""
    return result.stderr_excerpt or result.stdout_excerpt


def _doc_commands_text(item: RepoEvaluationResult, category: str) -> str:
    values = [
        f"{entry.source_file}: {entry.command.replace(chr(10), ' ')}"
        for entry in item.static.documentation.commands
        if entry.category == category
    ]
    return _join(values)


def render_repo_eval_markdown(results: list[RepoEvaluationResult]) -> str:
    lines: list[str] = []
    lines.append("# 开源代码仓软件开发体验评估报告")
    lines.append("")
    lines.append("| 仓库 | 编码风格是否有定义 | 代码检查是否支持 | 容器环境是否定义 | 容器环境本地可搭建 | 本地增量构建时间 | 本地代码检测时间 | 本地UT执行时间 | 代码检查规则数量 | 自动修复是否具备 | AI辅助代码检视是否支持 | PR执行时长平均值 | 单次PR资源CPU/NPU消耗量 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for item in results:
        lines.append(
            "| {repo} | {style} | {check} | {container_defined} | {container_ready} | {build} | {lint} | {ut} | {rules} | {fix} | {ai} | {pr} | {resource} |".format(
                repo=item.repo,
                style=_bool_text(item.static.style_defined),
                check=_bool_text(item.static.code_check_supported),
                container_defined=_bool_text(item.static.container_environment.defined),
                container_ready=_bool_text(
                    item.static.container_environment.setup_supported_locally
                ),
                build=_metric_duration_text(item.incremental_build),
                lint=_metric_duration_text(item.code_check),
                ut=_metric_duration_text(item.unit_test),
                rules=item.static.rule_count_estimate or "N/A",
                fix=_bool_text(item.static.auto_fix_supported),
                ai=_bool_text(item.pr_metrics.ai_review_supported),
                pr=_duration_text(item.pr_metrics.average_duration_sec),
                resource=_resource_text(item),
            )
        )
    lines.append("")

    issue_counter = Counter()
    for item in results:
        issue_counter.update(issue.category for issue in item.documentation_issues)

    lines.append("## Markdown 文档改进建议总览")
    lines.append("")
    if issue_counter:
        lines.append("| 分类 | 数量 |")
        lines.append("| --- | --- |")
        for category, count in issue_counter.most_common():
            lines.append(f"| {category} | {count} |")
    else:
        lines.append("当前没有识别出 Markdown 说明与实际执行之间的明显差距。")
    lines.append("")

    for item in results:
        lines.append(f"## {item.repo}")
        lines.append("")
        lines.append(f"- 本地路径: `{item.local_path}`")
        lines.append(
            f"- Markdown 扫描: `{item.static.documentation.markdown_files_scanned}` 个文件"
        )
        lines.append(f"- Markdown 相关文件: {_join(item.static.documentation.relevant_files)}")
        lines.append(f"- 文档中的安装命令: {_doc_commands_text(item, 'install')}")
        lines.append(f"- 文档中的构建命令: {_doc_commands_text(item, 'build')}")
        lines.append(f"- 文档中的测试命令: {_doc_commands_text(item, 'test')}")
        lines.append(f"- 文档中的代码检测命令: {_doc_commands_text(item, 'check')}")
        lines.append(f"- 文档中的容器命令: {_doc_commands_text(item, 'container')}")
        lines.append(f"- 编码风格证据: {_join(item.static.style_evidence)}")
        lines.append(f"- 代码检查证据: {_join(item.static.check_tools)}")
        lines.append(
            f"- 容器环境: {_bool_text(item.static.container_environment.defined)} / {_bool_text(item.static.container_environment.setup_supported_locally)} / `{item.static.container_environment.preferred_strategy}`"
        )
        container_definitions = (
            item.static.container_environment.dockerfiles
            + item.static.container_environment.compose_files
            + item.static.container_environment.devcontainer_files
            + item.static.container_environment.reference_files
        )
        lines.append(f"- 容器定义文件: {_join(container_definitions)}")
        container_images = (
            item.static.container_environment.base_images
            + item.static.container_environment.workflow_images
        )
        lines.append(f"- 容器镜像线索: {_join(container_images)}")
        lines.append(
            f"- 容器准备命令: `{item.static.container_environment.inferred_setup_command or 'N/A'}`"
        )
        lines.append(
            f"- 容器环境说明: {item.static.container_environment.note or 'N/A'}"
        )
        lines.append(
            f"- 容器环境证据: {_join(item.static.container_environment.setup_evidence)}"
        )
        if item.static.container_environment.setup_blockers:
            lines.append(
                f"- 容器环境阻塞: {_join(item.static.container_environment.setup_blockers)}"
            )
        rule_details = [
            f"{detail.source}: {detail.count if detail.count is not None else 'N/A'} ({detail.note})"
            for detail in item.static.rule_count_details
        ]
        lines.append(f"- 规则统计明细: {_join(rule_details)}")
        lines.append(f"- 自动修复证据: {_join(item.static.auto_fix_evidence)}")
        lines.append(f"- AI 代码检视证据: {_join(item.pr_metrics.ai_review_evidence)}")
        lines.append(
            f"- PR 指标平台/时间窗: `{item.pr_metrics.remote_platform}` / 最近 `{item.pr_metrics.pr_window_days}` 天"
        )
        lines.append(
            f"- PR 采样数量/工作流数量: `{item.pr_metrics.sampled_pull_count}` / `{item.pr_metrics.workflow_run_count}`"
        )
        lines.append(
            f"- PR 执行时长: 平均 `{_duration_text(item.pr_metrics.average_duration_sec)}` / 中位 `{_duration_text(item.pr_metrics.median_duration_sec)}` / 最近一次 `{_duration_text(item.pr_metrics.latest_duration_sec)}`"
        )
        lines.append(
            f"- PR 采集说明: {item.pr_metrics.collection_note or 'N/A'}"
        )
        lines.append(
            f"- 增量构建命令: `{item.incremental_build.command or 'N/A'}` -> {item.incremental_build.status}"
        )
        lines.append(
            f"- 增量构建实际执行耗时: `{_duration_text(item.incremental_build.duration_sec)}`"
        )
        lines.append(
            f"- 本地代码检测命令: `{item.code_check.command or 'N/A'}` -> {item.code_check.status}"
        )
        lines.append(
            f"- 本地代码检测实际执行耗时: `{_duration_text(item.code_check.duration_sec)}`"
        )
        lines.append(
            f"- UT 命令: `{item.unit_test.command or 'N/A'}` -> {item.unit_test.status}"
        )
        lines.append(
            f"- UT 实际执行耗时: `{_duration_text(item.unit_test.duration_sec)}`"
        )
        build_failure = _command_failure_text(item.incremental_build)
        if build_failure:
            lines.append(f"- 增量构建失败摘要: `{build_failure}`")
        check_failure = _command_failure_text(item.code_check)
        if check_failure:
            lines.append(f"- 代码检测失败摘要: `{check_failure}`")
        ut_failure = _command_failure_text(item.unit_test)
        if ut_failure:
            lines.append(f"- UT 失败摘要: `{ut_failure}`")
        lines.append(f"- PR Run 证据: {_join(item.pr_metrics.workflow_run_evidence)}")
        if item.static.inference_evidence:
            lines.append(f"- 命令推断依据: {_join(item.static.inference_evidence)}")
        if item.static.documentation.notes:
            lines.append(f"- 文档扫描备注: {_join(item.static.documentation.notes)}")
        if item.documentation_issues:
            lines.append("- Markdown 改进建议:")
            for issue in item.documentation_issues:
                evidence = "；".join(issue.evidence[:3]) if issue.evidence else "N/A"
                lines.append(
                    f"  - [{issue.severity}/{issue.root_cause}/{issue.category}] {issue.summary} | 证据: {evidence} | 建议: {issue.recommendation}"
                )
        else:
            lines.append("- Markdown 改进建议: N/A")
        if item.ai_summary.status != "disabled":
            lines.append(
                f"- AI 总结({item.ai_summary.provider}/{item.ai_summary.status}): {item.ai_summary.summary or item.ai_summary.stderr_excerpt or 'N/A'}"
            )
        if item.errors:
            lines.append(f"- 错误: {_join(item.errors)}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
