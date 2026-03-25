from __future__ import annotations

from collections import Counter
from html import escape

from .repo_eval_models import (
    CommandExecutionResult,
    DocumentationIssue,
    RepoEvaluationResult,
)


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


def _status_text(result: CommandExecutionResult) -> str:
    mapping = {
        "ok": "成功",
        "failed": "失败",
        "timeout": "超时",
        "error": "错误",
        "disabled": "未执行",
        "not_configured": "未配置",
    }
    return mapping.get(result.status, result.status)


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


def _join(values: list[str], limit: int = 8, separator: str = "<br>") -> str:
    if not values:
        return "N/A"
    items = values[:limit]
    if len(values) > limit:
        items.append(f"... (+{len(values) - limit})")
    return separator.join(items)


def _command_failure_text(result: CommandExecutionResult) -> str:
    if result.status not in {"failed", "timeout", "error"}:
        return ""
    return result.stderr_excerpt or result.stdout_excerpt


def _command_na_reason(label: str, result: CommandExecutionResult) -> str:
    if result.status == "ok":
        if result.duration_sec is None:
            return f"{label} 显示为 N/A，因为命令执行成功但没有返回耗时。"
        return ""
    if result.status == "not_configured":
        return f"{label} 显示为 N/A，因为当前没有配置或推断出可执行命令。"
    if result.status == "disabled":
        return f"{label} 显示为 N/A，因为本次运行禁用了本地命令执行。"
    if result.status in {"failed", "timeout", "error"}:
        detail = _command_failure_text(result)
        suffix = f" 失败摘要: {detail}" if detail else ""
        return (
            f"{label} 显示为 N/A，因为命令执行{_status_text(result)}。{suffix}".strip()
        )
    return f"{label} 显示为 N/A，因为命令状态为 `{result.status}`。"


def _pr_duration_na_reason(item: RepoEvaluationResult) -> str:
    metrics = item.pr_metrics
    if metrics.average_duration_sec is not None:
        return ""
    reasons: list[str] = []
    if metrics.remote_platform == "gitcode":
        reasons.append(
            "当前 GitCode 适配只采集 PR 评论与 AI 检视信号，尚未采集 workflow 时长。"
        )
    if metrics.collection_note:
        reasons.append(metrics.collection_note)
    elif metrics.workflow_run_count == 0:
        reasons.append("时间窗内没有可用的 GitHub Actions workflow 样本。")
    elif metrics.sampled_pull_count == 0:
        reasons.append("时间窗内没有可用的 PR 样本。")
    else:
        reasons.append("已拿到 PR 或 workflow 样本，但没有形成可计算的时长数据。")
    workflow_errors = [
        error
        for error in item.errors
        if "workflow runs" in error.lower() or "pr review signals" in error.lower()
    ]
    reasons.extend(workflow_errors)
    return "；".join(dict.fromkeys(reason for reason in reasons if reason))


def _pr_resource_na_reason(item: RepoEvaluationResult) -> str:
    metrics = item.pr_metrics
    if (
        metrics.actual_cpu_seconds is not None
        or metrics.actual_npu_seconds is not None
        or metrics.estimated_cpu_core_minutes is not None
        or metrics.estimated_npu_card_minutes is not None
    ):
        return ""
    if metrics.remote_platform == "gitcode":
        return "PR 资源显示为 N/A，因为当前 GitCode 适配未采集 workflow job 资源指标。"
    if metrics.workflow_run_count == 0:
        return "PR 资源显示为 N/A，因为没有可用于估算资源的 workflow job 样本。"
    return "PR 资源显示为 N/A，因为 workflow job 标签或时长不足以估算 CPU/NPU 消耗。"


def _na_reason_lines(item: RepoEvaluationResult) -> list[str]:
    reasons = [
        _command_na_reason("本地增量构建时间", item.incremental_build),
        _command_na_reason("本地代码检测时间", item.code_check),
        _command_na_reason("本地 UT 执行时间", item.unit_test),
        _pr_duration_na_reason(item),
        _pr_resource_na_reason(item),
    ]
    return [reason for reason in reasons if reason]


def _doc_commands(item: RepoEvaluationResult, category: str) -> list[str]:
    return [
        f"{entry.source_file}: {entry.command.replace(chr(10), ' ')}"
        for entry in item.static.documentation.commands
        if entry.category == category
    ]


def _issue_text(issue: DocumentationIssue) -> str:
    evidence = "；".join(issue.evidence[:3]) if issue.evidence else "N/A"
    return (
        f"[{issue.severity}/{issue.root_cause}/{issue.category}] {issue.summary} | "
        f"证据: {evidence} | 建议: {issue.recommendation}"
    )


def _html_status_class(status: str) -> str:
    return {
        "ok": "ok",
        "failed": "failed",
        "timeout": "timeout",
        "error": "error",
        "disabled": "disabled",
        "not_configured": "disabled",
    }.get(status, "disabled")


def _status_badge(result: CommandExecutionResult) -> str:
    label = _status_text(result)
    return (
        f'<span class="status {escape(_html_status_class(result.status))}">'
        f"{escape(label)}"
        "</span>"
    )


def _render_issue_overview_markdown(results: list[RepoEvaluationResult]) -> list[str]:
    counter = Counter()
    for item in results:
        counter.update(issue.category for issue in item.documentation_issues)

    lines = ["## Markdown 改进建议总览", ""]
    if not counter:
        lines.append("当前没有识别出 Markdown 与实际执行之间的明显偏差。")
        lines.append("")
        return lines

    lines.append("| 分类 | 数量 |")
    lines.append("| --- | --- |")
    for category, count in counter.most_common():
        lines.append(f"| {category} | {count} |")
    lines.append("")
    return lines


def render_repo_eval_markdown(results: list[RepoEvaluationResult]) -> str:
    lines: list[str] = []
    lines.append("# 开源代码仓开发体验评估报告")
    lines.append("")
    lines.append(
        "| 仓库 | 编码风格是否有定义 | 代码检测是否支持 | 容器环境是否定义 | 容器环境本地可搭建 | 本地增量构建时间 | 本地代码检测时间 | 本地UT执行时间 | 代码检查规则数量 | 自动修复是否具备 | AI辅助代码检视是否支持 | PR执行时长平均值 | 单次PR资源CPU/NPU消耗量 |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )
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

    lines.extend(_render_issue_overview_markdown(results))

    for item in results:
        lines.append(f"## {item.repo}")
        lines.append("")
        lines.append(f"- 本地路径: `{item.local_path}`")
        lines.append(
            f"- Markdown 扫描文件数: `{item.static.documentation.markdown_files_scanned}`"
        )
        lines.append(
            f"- Markdown 相关文件: {_join(item.static.documentation.relevant_files, separator='；')}"
        )
        lines.append(f"- 编码风格是否定义: {_bool_text(item.static.style_defined)}")
        lines.append(
            f"- 编码风格证据: {_join(item.static.style_evidence, separator='；')}"
        )
        lines.append(
            f"- 代码检测是否支持: {_bool_text(item.static.code_check_supported)}"
        )
        lines.append(
            f"- 代码检测证据: {_join(item.static.check_tools, separator='；')}"
        )
        lines.append(
            f"- 自动修复是否具备: {_bool_text(item.static.auto_fix_supported)}"
        )
        lines.append(
            f"- 自动修复证据: {_join(item.static.auto_fix_evidence, separator='；')}"
        )
        lines.append(
            f"- 容器环境: {_bool_text(item.static.container_environment.defined)} / {_bool_text(item.static.container_environment.setup_supported_locally)} / `{item.static.container_environment.preferred_strategy}`"
        )
        lines.append(
            f"- 容器定义文件: {_join(item.static.container_environment.dockerfiles + item.static.container_environment.compose_files + item.static.container_environment.devcontainer_files + item.static.container_environment.reference_files, separator='；')}"
        )
        lines.append(
            f"- 容器镜像线索: {_join(item.static.container_environment.base_images + item.static.container_environment.workflow_images, separator='；')}"
        )
        lines.append(
            f"- 容器准备命令: `{item.static.container_environment.inferred_setup_command or 'N/A'}`"
        )
        lines.append(
            f"- 容器环境说明: {item.static.container_environment.note or 'N/A'}"
        )
        if item.static.container_environment.setup_blockers:
            lines.append(
                f"- 容器环境阻塞: {_join(item.static.container_environment.setup_blockers, separator='；')}"
            )
        rule_details = [
            f"{detail.source}: {detail.count if detail.count is not None else 'N/A'} ({detail.note})"
            for detail in item.static.rule_count_details
        ]
        lines.append(f"- 规则统计明细: {_join(rule_details, separator='；')}")
        lines.append(
            f"- 文档中的安装命令: {_join(_doc_commands(item, 'install'), separator='；')}"
        )
        lines.append(
            f"- 文档中的构建命令: {_join(_doc_commands(item, 'build'), separator='；')}"
        )
        lines.append(
            f"- 文档中的测试命令: {_join(_doc_commands(item, 'test'), separator='；')}"
        )
        lines.append(
            f"- 文档中的代码检测命令: {_join(_doc_commands(item, 'check'), separator='；')}"
        )
        lines.append(
            f"- 文档中的容器命令: {_join(_doc_commands(item, 'container'), separator='；')}"
        )
        lines.append(
            f"- 增量构建命令: `{item.incremental_build.command or 'N/A'}` -> {_status_text(item.incremental_build)}"
        )
        lines.append(
            f"- 增量构建实际探测耗时: `{_duration_text(item.incremental_build.duration_sec)}`"
        )
        lines.append(
            f"- 本地代码检测命令: `{item.code_check.command or 'N/A'}` -> {_status_text(item.code_check)}"
        )
        lines.append(
            f"- 本地代码检测实际探测耗时: `{_duration_text(item.code_check.duration_sec)}`"
        )
        lines.append(
            f"- UT 命令: `{item.unit_test.command or 'N/A'}` -> {_status_text(item.unit_test)}"
        )
        lines.append(
            f"- UT 实际探测耗时: `{_duration_text(item.unit_test.duration_sec)}`"
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
        lines.append(
            f"- PR 指标平台 / 时间窗: `{item.pr_metrics.remote_platform}` / 最近 `{item.pr_metrics.pr_window_days}` 天"
        )
        lines.append(
            f"- PR 采样数量 / Workflow 数量: `{item.pr_metrics.sampled_pull_count}` / `{item.pr_metrics.workflow_run_count}`"
        )
        lines.append(
            f"- PR 执行时长: 平均 `{_duration_text(item.pr_metrics.average_duration_sec)}` / 中位 `{_duration_text(item.pr_metrics.median_duration_sec)}` / 最近一次 `{_duration_text(item.pr_metrics.latest_duration_sec)}`"
        )
        lines.append(f"- PR 资源消耗: {_resource_text(item)}")
        na_reasons = _na_reason_lines(item)
        if na_reasons:
            lines.append("- N/A 原因分析:")
            for reason in na_reasons:
                lines.append(f"  - {reason}")
        lines.append(
            f"- AI 代码检视证据: {_join(item.pr_metrics.ai_review_evidence, separator='；')}"
        )
        lines.append(f"- PR 采集说明: {item.pr_metrics.collection_note or 'N/A'}")
        if item.pr_metrics.workflow_run_evidence:
            lines.append(
                f"- PR Run 证据: {_join(item.pr_metrics.workflow_run_evidence, separator='；')}"
            )
        if item.static.inference_evidence:
            lines.append(
                f"- 命令推断依据: {_join(item.static.inference_evidence, separator='；')}"
            )
        if item.static.documentation.notes:
            lines.append(
                f"- 文档扫描备注: {_join(item.static.documentation.notes, separator='；')}"
            )
        if item.documentation_issues:
            lines.append("- Markdown 改进建议:")
            for issue in item.documentation_issues:
                lines.append(f"  - {_issue_text(issue)}")
        else:
            lines.append("- Markdown 改进建议: N/A")
        if item.ai_summary.status != "disabled":
            lines.append(
                f"- AI 总结({item.ai_summary.provider}/{item.ai_summary.status}): {item.ai_summary.summary or item.ai_summary.stderr_excerpt or 'N/A'}"
            )
        if item.errors:
            lines.append(f"- 错误: {_join(item.errors, separator='；')}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _summary_metrics(results: list[RepoEvaluationResult]) -> list[tuple[str, str]]:
    total_issues = sum(len(item.documentation_issues) for item in results)
    return [
        ("仓库数", str(len(results))),
        ("定义编码风格", str(sum(1 for item in results if item.static.style_defined))),
        (
            "支持代码检测",
            str(sum(1 for item in results if item.static.code_check_supported)),
        ),
        (
            "容器可本地搭建",
            str(
                sum(
                    1
                    for item in results
                    if item.static.container_environment.setup_supported_locally
                )
            ),
        ),
        ("文档问题条数", str(total_issues)),
    ]


def _render_html_summary_table(results: list[RepoEvaluationResult]) -> str:
    rows: list[str] = []
    for item in results:
        rows.append(
            "<tr>"
            f"<td>{escape(item.repo)}</td>"
            f"<td>{escape(_bool_text(item.static.style_defined))}</td>"
            f"<td>{escape(_bool_text(item.static.code_check_supported))}</td>"
            f"<td>{escape(_bool_text(item.static.container_environment.defined))}</td>"
            f"<td>{escape(_bool_text(item.static.container_environment.setup_supported_locally))}</td>"
            f"<td>{escape(_metric_duration_text(item.incremental_build))}</td>"
            f"<td>{escape(_metric_duration_text(item.code_check))}</td>"
            f"<td>{escape(_metric_duration_text(item.unit_test))}</td>"
            f"<td>{escape(str(item.static.rule_count_estimate or 'N/A'))}</td>"
            f"<td>{escape(_bool_text(item.static.auto_fix_supported))}</td>"
            f"<td>{escape(_bool_text(item.pr_metrics.ai_review_supported))}</td>"
            f"<td>{escape(_duration_text(item.pr_metrics.average_duration_sec))}</td>"
            f"<td>{escape(_resource_text(item))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_html_list(title: str, values: list[str]) -> str:
    if not values:
        return f'<div class="kv"><div class="k">{escape(title)}</div><div class="v">N/A</div></div>'
    items = "".join(f"<li>{escape(value)}</li>" for value in values)
    return (
        f'<div class="kv"><div class="k">{escape(title)}</div>'
        f'<div class="v"><ul>{items}</ul></div></div>'
    )


def _render_html_repo_panel(item: RepoEvaluationResult, index: int) -> str:
    issue_items = (
        "".join(
            f"<li>{escape(_issue_text(issue))}</li>"
            for issue in item.documentation_issues
        )
        if item.documentation_issues
        else "<li>N/A</li>"
    )
    error_items = (
        "".join(f"<li>{escape(value)}</li>" for value in item.errors)
        if item.errors
        else "<li>N/A</li>"
    )
    rule_items = [
        f"{detail.source}: {detail.count if detail.count is not None else 'N/A'} ({detail.note})"
        for detail in item.static.rule_count_details
    ]
    return f"""
<section class="repo-panel {"active" if index == 0 else ""}" id="repo-panel-{index}">
  <div class="panel-grid">
    <div class="card">
      <h3>概览</h3>
      <div class="kv"><div class="k">仓库</div><div class="v">{escape(item.repo)}</div></div>
      <div class="kv"><div class="k">本地路径</div><div class="v"><code>{escape(item.local_path)}</code></div></div>
      <div class="kv"><div class="k">Markdown 扫描文件数</div><div class="v">{item.static.documentation.markdown_files_scanned}</div></div>
      <div class="kv"><div class="k">编码风格是否定义</div><div class="v">{escape(_bool_text(item.static.style_defined))}</div></div>
      <div class="kv"><div class="k">代码检测是否支持</div><div class="v">{escape(_bool_text(item.static.code_check_supported))}</div></div>
      <div class="kv"><div class="k">自动修复是否具备</div><div class="v">{escape(_bool_text(item.static.auto_fix_supported))}</div></div>
      <div class="kv"><div class="k">容器环境</div><div class="v">{escape(_bool_text(item.static.container_environment.defined))} / {escape(_bool_text(item.static.container_environment.setup_supported_locally))} / <code>{escape(item.static.container_environment.preferred_strategy)}</code></div></div>
      <div class="kv"><div class="k">规则数量估算</div><div class="v">{escape(str(item.static.rule_count_estimate or "N/A"))}</div></div>
    </div>
    <div class="card">
      <h3>本地探测结果</h3>
      <div class="kv"><div class="k">增量构建</div><div class="v">{_status_badge(item.incremental_build)} <code>{escape(item.incremental_build.command or "N/A")}</code> ({escape(_duration_text(item.incremental_build.duration_sec))})</div></div>
      <div class="kv"><div class="k">代码检测</div><div class="v">{_status_badge(item.code_check)} <code>{escape(item.code_check.command or "N/A")}</code> ({escape(_duration_text(item.code_check.duration_sec))})</div></div>
      <div class="kv"><div class="k">UT</div><div class="v">{_status_badge(item.unit_test)} <code>{escape(item.unit_test.command or "N/A")}</code> ({escape(_duration_text(item.unit_test.duration_sec))})</div></div>
      <div class="kv"><div class="k">构建失败摘要</div><div class="v">{escape(_command_failure_text(item.incremental_build) or "N/A")}</div></div>
      <div class="kv"><div class="k">代码检测失败摘要</div><div class="v">{escape(_command_failure_text(item.code_check) or "N/A")}</div></div>
      <div class="kv"><div class="k">UT 失败摘要</div><div class="v">{escape(_command_failure_text(item.unit_test) or "N/A")}</div></div>
    </div>
    <div class="card">
      <h3>PR 流水线</h3>
      <div class="kv"><div class="k">平台 / 时间窗</div><div class="v"><code>{escape(item.pr_metrics.remote_platform)}</code> / 最近 {item.pr_metrics.pr_window_days} 天</div></div>
      <div class="kv"><div class="k">PR 采样 / Workflow</div><div class="v">{item.pr_metrics.sampled_pull_count} / {item.pr_metrics.workflow_run_count}</div></div>
      <div class="kv"><div class="k">PR 平均时长</div><div class="v">{escape(_duration_text(item.pr_metrics.average_duration_sec))}</div></div>
      <div class="kv"><div class="k">PR 中位时长</div><div class="v">{escape(_duration_text(item.pr_metrics.median_duration_sec))}</div></div>
      <div class="kv"><div class="k">最近一次 PR 时长</div><div class="v">{escape(_duration_text(item.pr_metrics.latest_duration_sec))}</div></div>
      <div class="kv"><div class="k">资源消耗</div><div class="v">{escape(_resource_text(item))}</div></div>
      <div class="kv"><div class="k">PR 采集说明</div><div class="v">{escape(item.pr_metrics.collection_note or "N/A")}</div></div>
    </div>
  </div>
  <div class="panel-grid">
    <div class="card">
      <h3>文档与命令</h3>
      {_render_html_list("Markdown 相关文件", item.static.documentation.relevant_files)}
      {_render_html_list("文档中的安装命令", _doc_commands(item, "install"))}
      {_render_html_list("文档中的构建命令", _doc_commands(item, "build"))}
      {_render_html_list("文档中的测试命令", _doc_commands(item, "test"))}
      {_render_html_list("文档中的代码检测命令", _doc_commands(item, "check"))}
      {_render_html_list("文档中的容器命令", _doc_commands(item, "container"))}
      {_render_html_list("文档扫描备注", item.static.documentation.notes)}
      {_render_html_list("命令推断依据", item.static.inference_evidence)}
    </div>
    <div class="card">
      <h3>证据与改进建议</h3>
      {_render_html_list("编码风格证据", item.static.style_evidence)}
      {_render_html_list("代码检测证据", item.static.check_tools)}
      {_render_html_list("自动修复证据", item.static.auto_fix_evidence)}
      {_render_html_list("规则统计明细", rule_items)}
      {_render_html_list("容器定义文件", item.static.container_environment.dockerfiles + item.static.container_environment.compose_files + item.static.container_environment.devcontainer_files + item.static.container_environment.reference_files)}
      {_render_html_list("容器镜像线索", item.static.container_environment.base_images + item.static.container_environment.workflow_images)}
      {_render_html_list("容器环境阻塞", item.static.container_environment.setup_blockers)}
      {_render_html_list("AI 代码检视证据", item.pr_metrics.ai_review_evidence)}
      {_render_html_list("PR Run 证据", item.pr_metrics.workflow_run_evidence)}
      {_render_html_list("N/A 原因分析", _na_reason_lines(item))}
    </div>
    <div class="card">
      <h3>Markdown 改进建议</h3>
      <ul>{issue_items}</ul>
      <h3>错误</h3>
      <ul>{error_items}</ul>
      <div class="kv"><div class="k">AI 总结</div><div class="v">{escape(item.ai_summary.summary or item.ai_summary.stderr_excerpt or "N/A")}</div></div>
    </div>
  </div>
</section>
"""


def render_repo_eval_html(results: list[RepoEvaluationResult]) -> str:
    metrics_html = "".join(
        f'<div class="metric"><div class="metric-label">{escape(label)}</div><div class="metric-value">{escape(value)}</div></div>'
        for label, value in _summary_metrics(results)
    )
    issue_counter = Counter()
    for item in results:
        issue_counter.update(issue.category for issue in item.documentation_issues)
    issue_rows = (
        "".join(
            f"<tr><td>{escape(category)}</td><td>{count}</td></tr>"
            for category, count in issue_counter.most_common()
        )
        if issue_counter
        else '<tr><td colspan="2">当前没有识别出 Markdown 与实际执行之间的明显偏差。</td></tr>'
    )
    tab_buttons = "".join(
        f'<button class="repo-tab {"active" if index == 0 else ""}" onclick="showRepoTab({index})">{escape(item.repo)}</button>'
        for index, item in enumerate(results)
    )
    panels = "".join(
        _render_html_repo_panel(item, index) for index, item in enumerate(results)
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>开源代码仓开发体验评估报告</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --panel: #fffdf8;
      --ink: #1e2724;
      --muted: #5a665f;
      --accent: #186a5b;
      --accent-soft: #dceee7;
      --border: #d8d2c8;
      --ok: #1f7a4d;
      --warn: #b96d00;
      --bad: #b42318;
      --disabled: #667085;
      --shadow: 0 18px 40px rgba(24, 34, 33, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #f7dfc5 0, transparent 26%),
        radial-gradient(circle at top right, #d4ebe2 0, transparent 30%),
        var(--bg);
    }}
    .page {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.1;
      letter-spacing: -0.03em;
    }}
    .subtitle {{
      color: var(--muted);
      margin-bottom: 24px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }}
    .metric, .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }}
    .metric {{
      padding: 18px 20px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .metric-value {{
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
    }}
    .section {{
      margin-top: 24px;
    }}
    .section-title {{
      margin: 0 0 12px;
      font-size: 20px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border-radius: 18px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 12px 14px;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: #f8f4ec;
      font-weight: 700;
    }}
    .repo-tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 12px 0 18px;
    }}
    .repo-tab {{
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.7);
      color: var(--muted);
      padding: 10px 14px;
      border-radius: 999px;
      cursor: pointer;
      transition: 160ms ease;
      font-weight: 600;
    }}
    .repo-tab.active {{
      color: white;
      background: linear-gradient(135deg, #1d6f5f, #0f4f43);
      border-color: transparent;
    }}
    .repo-panel {{
      display: none;
    }}
    .repo-panel.active {{
      display: block;
      animation: fadeIn 180ms ease;
    }}
    .panel-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 14px;
      margin-bottom: 14px;
    }}
    .card {{
      padding: 18px 18px 8px;
    }}
    .card h3 {{
      margin: 0 0 14px;
      font-size: 18px;
    }}
    .kv {{
      display: grid;
      grid-template-columns: 140px 1fr;
      gap: 10px;
      padding: 8px 0;
      border-top: 1px solid rgba(216, 210, 200, 0.65);
    }}
    .kv:first-of-type {{
      border-top: 0;
    }}
    .k {{
      color: var(--muted);
      font-size: 13px;
    }}
    .v {{
      min-width: 0;
      word-break: break-word;
    }}
    ul {{
      margin: 6px 0 0 18px;
      padding: 0;
    }}
    li {{
      margin-bottom: 6px;
    }}
    code {{
      font-family: "Cascadia Code", "Consolas", monospace;
      background: #f2eee6;
      padding: 2px 5px;
      border-radius: 6px;
      font-size: 12px;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      padding: 2px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      margin-right: 8px;
    }}
    .status.ok {{ background: #dcfae6; color: var(--ok); }}
    .status.failed, .status.error {{ background: #fde7e7; color: var(--bad); }}
    .status.timeout {{ background: #fff1d6; color: var(--warn); }}
    .status.disabled {{ background: #eceff3; color: var(--disabled); }}
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @media (max-width: 900px) {{
      .page {{ padding: 20px 14px 28px; }}
      h1 {{ font-size: 28px; }}
      .kv {{ grid-template-columns: 1fr; gap: 4px; }}
      th, td {{ font-size: 13px; padding: 10px 10px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <h1>开源代码仓开发体验评估报告</h1>
    <div class="subtitle">汇总本地编码、构建、测试、代码检测、容器环境与 PR 流水线指标。</div>

    <div class="metrics">{metrics_html}</div>

    <section class="section">
      <h2 class="section-title">仓库汇总</h2>
      <table>
        <thead>
          <tr>
            <th>仓库</th>
            <th>编码风格</th>
            <th>代码检测</th>
            <th>容器定义</th>
            <th>容器可搭建</th>
            <th>构建时间</th>
            <th>检测时间</th>
            <th>UT 时间</th>
            <th>规则数</th>
            <th>自动修复</th>
            <th>AI 代码检视</th>
            <th>PR 平均时长</th>
            <th>PR 资源</th>
          </tr>
        </thead>
        <tbody>
          {_render_html_summary_table(results)}
        </tbody>
      </table>
    </section>

    <section class="section">
      <h2 class="section-title">Markdown 改进建议总览</h2>
      <table>
        <thead>
          <tr><th>分类</th><th>数量</th></tr>
        </thead>
        <tbody>
          {issue_rows}
        </tbody>
      </table>
    </section>

    <section class="section">
      <h2 class="section-title">仓库详情</h2>
      <div class="repo-tabs">{tab_buttons}</div>
      {panels}
    </section>
  </div>
  <script>
    function showRepoTab(index) {{
      const tabs = document.querySelectorAll('.repo-tab');
      const panels = document.querySelectorAll('.repo-panel');
      tabs.forEach((tab, i) => tab.classList.toggle('active', i === index));
      panels.forEach((panel, i) => panel.classList.toggle('active', i === index));
    }}
  </script>
</body>
</html>
"""
