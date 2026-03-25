from __future__ import annotations

from collections import Counter
from html import escape

from .repo_eval_models import (
    CommandExecutionResult,
    DocumentationCommand,
    DocumentationIssue,
    PullRequestMetrics,
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


def _doc_commands(
    item: RepoEvaluationResult, category: str
) -> list[DocumentationCommand]:
    return [
        entry
        for entry in item.static.documentation.commands
        if entry.category == category
    ]


def _issue_text(issue: DocumentationIssue) -> str:
    evidence = "；".join(issue.evidence[:3]) if issue.evidence else "N/A"
    return (
        f"[{issue.severity}/{issue.root_cause}/{issue.category}] {issue.summary} | "
        f"证据: {evidence} | 建议: {issue.recommendation}"
    )


def _issue_map(item: RepoEvaluationResult) -> dict[str, list[DocumentationIssue]]:
    grouped: dict[str, list[DocumentationIssue]] = {}
    for issue in item.documentation_issues:
        grouped.setdefault(issue.category, []).append(issue)
    return grouped


def _issue_evidence(
    item: RepoEvaluationResult,
    categories: tuple[str, ...],
    limit: int = 3,
) -> list[str]:
    evidence: list[str] = []
    grouped = _issue_map(item)
    for category in categories:
        for issue in grouped.get(category, [])[:limit]:
            evidence.append(issue.summary)
            evidence.extend(issue.evidence[:2])
    return list(dict.fromkeys(evidence))[:limit]


def _doc_command_strings(item: RepoEvaluationResult, category: str) -> list[str]:
    return [
        f"{entry.source_file}: {entry.command.replace(chr(10), ' ')}"
        for entry in _doc_commands(item, category)
    ]


def _command_source_evidence(
    item: RepoEvaluationResult,
    metric_key: str,
    result: CommandExecutionResult,
    doc_category: str,
) -> list[str]:
    evidence: list[str] = []
    if result.command:
        evidence.append(f"命令: {result.command}")
    if result.returncode is not None:
        evidence.append(f"返回码: {result.returncode}")
    if result.duration_sec is not None:
        evidence.append(f"实际耗时: {_duration_text(result.duration_sec)}")

    inferred = {
        "build": item.static.inferred_build_command,
        "test": item.static.inferred_unit_test_command,
        "check": item.static.inferred_code_check_command,
    }.get(metric_key, "")
    if inferred and inferred == result.command:
        evidence.append("命令来源: 仓库结构推断")

    matched_docs = [
        f"文档命中: {entry.source_file}"
        for entry in _doc_commands(item, doc_category)
        if entry.command == result.command
    ]
    evidence.extend(matched_docs[:2])

    if result.stdout_excerpt:
        evidence.append(f"输出摘要: {result.stdout_excerpt}")
    return list(dict.fromkeys(evidence))


def _root_cause_entry(
    category: str, summary: str, evidence: list[str]
) -> dict[str, object]:
    return {
        "category": category,
        "summary": summary,
        "evidence": [value for value in evidence if value][:4],
    }


def _build_local_metric_root_causes(
    item: RepoEvaluationResult,
    metric_key: str,
    label: str,
    result: CommandExecutionResult,
    doc_category: str,
) -> list[dict[str, object]]:
    if result.status == "ok":
        return []

    docs = _doc_commands(item, doc_category)
    issue_groups = _issue_map(item)
    text = (result.stderr_excerpt or result.stdout_excerpt or "").lower()
    command = result.command or "N/A"
    base_evidence = [
        f"命令: {command}",
        f"状态: {_status_text(result)}",
    ]
    if result.duration_sec is not None:
        base_evidence.append(f"探测耗时: {_duration_text(result.duration_sec)}")
    if result.stderr_excerpt or result.stdout_excerpt:
        base_evidence.append(
            f"失败摘要: {(result.stderr_excerpt or result.stdout_excerpt)[:220]}"
        )
    if docs:
        base_evidence.append(f"文档命令数: {len(docs)}")

    causes: list[dict[str, object]] = []

    if result.status == "disabled":
        causes.append(
            _root_cause_entry(
                "本地执行已禁用",
                f"{label} 当前为 N/A，因为本次运行禁用了本地命令执行。",
                base_evidence,
            )
        )
        return causes

    if result.status == "not_configured":
        missing_summary = {
            "build": "缺少一键式构建脚本",
            "test": "缺少 UT 脚本或统一测试入口",
            "check": "缺少代码检测入口",
        }[metric_key]
        if not docs:
            causes.append(
                _root_cause_entry(
                    missing_summary,
                    f"{label} 当前为 N/A，因为仓库里没有发现可直接执行的 {label} 命令，也没有在 Markdown 中给出清晰入口。",
                    base_evidence
                    + _issue_evidence(
                        item,
                        (
                            "missing_build_command_docs",
                            "missing_test_command_docs",
                            "missing_code_check_docs",
                        ),
                    ),
                )
            )
        else:
            causes.append(
                _root_cause_entry(
                    "文档说明不清晰",
                    f"{label} 当前为 N/A，虽然文档提到了相关步骤，但程序没有识别出稳定可执行的统一命令入口。",
                    base_evidence + _doc_command_strings(item, doc_category)[:3],
                )
            )
        return causes

    if result.status == "timeout":
        causes.append(
            _root_cause_entry(
                "本地执行超时",
                f"{label} 当前为 N/A，因为命令在设定时间内没有完成。",
                base_evidence,
            )
        )

    if any(
        token in text
        for token in (
            "pull access denied",
            "manifest unknown",
            "403 forbidden",
            "image not found",
            "unauthorized",
            "docker pull",
        )
    ):
        causes.append(
            _root_cause_entry(
                "镜像环境下载失败",
                f"{label} 无法完成，因为镜像拉取或容器资源下载失败。",
                base_evidence + _doc_command_strings(item, "container")[:2],
            )
        )

    if (
        item.static.container_environment.defined
        and not item.static.container_environment.runnable_definition_present
    ) or issue_groups.get("container_docs_not_self_contained"):
        causes.append(
            _root_cause_entry(
                "无可运行镜像或容器定义",
                f"{label} 依赖容器环境，但仓库只提到了 Docker 路径，没有提供可直接运行的镜像定义或构建文件。",
                base_evidence
                + item.static.container_environment.reference_files[:2]
                + item.static.container_environment.setup_blockers[:2],
            )
        )

    if issue_groups.get("external_manual_dependency"):
        causes.append(
            _root_cause_entry(
                "外部依赖受限",
                f"{label} 依赖外部站点登录、手工下载或私有资源，自动化环境无法直接复现。",
                base_evidence + _issue_evidence(item, ("external_manual_dependency",)),
            )
        )

    if issue_groups.get("missing_environment_prerequisite"):
        causes.append(
            _root_cause_entry(
                "环境前置条件缺失",
                f"{label} 依赖额外的 GPU/NPU、驱动、容器 runtime 或系统环境，但当前机器不满足前置条件。",
                base_evidence
                + _issue_evidence(item, ("missing_environment_prerequisite",)),
            )
        )

    if issue_groups.get("missing_version_prerequisite"):
        causes.append(
            _root_cause_entry(
                "版本前置条件不明确",
                f"{label} 当前失败，说明文档没有把 Python/依赖版本前置条件写清楚。",
                base_evidence
                + _issue_evidence(item, ("missing_version_prerequisite",)),
            )
        )

    if issue_groups.get("missing_dependency_step"):
        causes.append(
            _root_cause_entry(
                "依赖准备步骤缺失",
                f"{label} 当前失败，说明文档缺少必要的依赖安装或环境准备步骤。",
                base_evidence + _issue_evidence(item, ("missing_dependency_step",)),
            )
        )

    if issue_groups.get("missing_tooling_prerequisite"):
        causes.append(
            _root_cause_entry(
                "工具前置条件缺失",
                f"{label} 当前失败，说明文档没有明确安装相关工具链，例如 pre-commit、uv、pytest 或 docker。",
                base_evidence
                + _issue_evidence(item, ("missing_tooling_prerequisite",)),
            )
        )

    if issue_groups.get("repository_script_issue"):
        causes.append(
            _root_cause_entry(
                "仓库脚本问题",
                f"{label} 当前失败的直接根因在仓库脚本本身，例如 CRLF/LF 行尾、脚本语法或内容错误，而不是单纯的 Markdown 说明不清楚。",
                base_evidence + _issue_evidence(item, ("repository_script_issue",)),
            )
        )

    doc_issue_categories = (
        "missing_build_command_docs",
        "missing_test_command_docs",
        "missing_code_check_docs",
        "container_docs_not_self_contained",
        "execution_failure_needs_manual_triage",
    )
    if any(issue_groups.get(category) for category in doc_issue_categories):
        causes.append(
            _root_cause_entry(
                "README/开发文档说明不清晰",
                f"{label} 当前失败或不可得，报告同时发现 Markdown 文档与仓库实际行为之间存在漂移或缺漏。",
                base_evidence + _issue_evidence(item, doc_issue_categories),
            )
        )

    if not causes:
        causes.append(
            _root_cause_entry(
                "命令执行失败待人工排查",
                f"{label} 当前为 N/A，但尚未归类到更具体的失败维度。",
                base_evidence,
            )
        )

    deduped: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for cause in causes:
        key = (str(cause["category"]), str(cause["summary"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cause)
    return deduped


def _build_pr_root_causes(item: RepoEvaluationResult) -> list[dict[str, object]]:
    metrics = item.pr_metrics
    causes: list[dict[str, object]] = []
    evidence = [
        f"平台: {metrics.remote_platform}",
        f"时间窗口: 最近 {metrics.pr_window_days} 天",
        f"PR 样本数: {metrics.sampled_pull_count}",
        f"Workflow 样本数: {metrics.workflow_run_count}",
    ]

    if metrics.average_duration_sec is None:
        if metrics.remote_platform == "gitcode":
            causes.append(
                _root_cause_entry(
                    "PR 流水线指标暂未接入",
                    "当前 GitCode 适配只支持 PR 评论与 AI 检视信号采集，尚未接入 workflow 时长与资源指标。",
                    evidence
                    + ([metrics.collection_note] if metrics.collection_note else []),
                )
            )
        elif "匿名访问" in (metrics.collection_note or ""):
            causes.append(
                _root_cause_entry(
                    "缺少 GitHub Token 或受限于匿名配额",
                    "PR 平均时长当前为 N/A，远端采集使用匿名访问时可能受 rate limit 影响。",
                    evidence
                    + ([metrics.collection_note] if metrics.collection_note else []),
                )
            )
        elif metrics.workflow_run_count == 0:
            causes.append(
                _root_cause_entry(
                    "时间窗口内无 PR Workflow 样本",
                    "PR 平均时长当前为 N/A，因为指定时间窗口内没有可用的 workflow 运行样本。",
                    evidence
                    + ([metrics.collection_note] if metrics.collection_note else []),
                )
            )
        elif metrics.sampled_pull_count == 0:
            causes.append(
                _root_cause_entry(
                    "时间窗口内无 PR 样本",
                    "PR 平均时长当前为 N/A，因为指定时间窗口内没有可用的 PR 样本。",
                    evidence
                    + ([metrics.collection_note] if metrics.collection_note else []),
                )
            )

    if (
        metrics.actual_cpu_seconds is None
        and metrics.actual_npu_seconds is None
        and metrics.estimated_cpu_core_minutes is None
        and metrics.estimated_npu_card_minutes is None
    ):
        if metrics.remote_platform == "gitcode":
            causes.append(
                _root_cause_entry(
                    "PR 资源指标暂未接入",
                    "当前 GitCode 适配尚未接入 workflow job 级别的 CPU/NPU 资源采集。",
                    evidence
                    + ([metrics.collection_note] if metrics.collection_note else []),
                )
            )
        elif metrics.workflow_run_count == 0:
            causes.append(
                _root_cause_entry(
                    "无可估算 PR 资源的 workflow 样本",
                    "PR CPU/NPU 当前为 N/A，因为没有可用于估算的 workflow job 样本。",
                    evidence
                    + ([metrics.collection_note] if metrics.collection_note else []),
                )
            )

    deduped: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for cause in causes:
        key = (str(cause["category"]), str(cause["summary"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cause)
    return deduped


def _build_metric_success_evidence(
    item: RepoEvaluationResult,
    metric_key: str,
    label: str,
    result: CommandExecutionResult,
    doc_category: str,
) -> list[str]:
    if result.status != "ok":
        return []
    evidence = _command_source_evidence(item, metric_key, result, doc_category)
    if label == "本地代码检测时间" and item.static.check_tools:
        evidence.append(
            f"检测工具: {_join(item.static.check_tools, limit=4, separator='；')}"
        )
    if (
        label == "本地增量构建时间"
        and item.static.container_environment.inferred_setup_command
    ):
        evidence.append(
            f"容器/环境线索: {item.static.container_environment.preferred_strategy}"
        )
    if label == "本地 UT 执行时间" and item.static.inferred_unit_test_command:
        evidence.append("测试入口已被仓库结构或文档识别")
    return evidence[:6]


def _build_pr_success_evidence(metrics: PullRequestMetrics) -> list[str]:
    if metrics.average_duration_sec is None:
        return []
    evidence = [
        f"时间窗口: 最近 {metrics.pr_window_days} 天",
        f"PR 样本数: {metrics.sampled_pull_count}",
        f"Workflow 样本数: {metrics.workflow_run_count}",
        f"平均时长: {_duration_text(metrics.average_duration_sec)}",
    ]
    evidence.extend(metrics.workflow_run_evidence[:2])
    return evidence[:6]


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
        "| 仓库 | 编码风格是否有定义 | 代码检测是否支持 | 容器环境是否定义 | 容器环境本地可搭建 | 本地增量构建时间 | 本地代码检测时间 | 本地 UT 执行时间 | 代码检查规则数量 | 自动修复是否具备 | AI 辅助代码检视是否支持 | PR 执行时长平均值 | 单次 PR 资源 CPU/NPU 消耗量 |"
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
        lines.append("### 基础概览")
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

        lines.append("")
        lines.append("### 文档与命令发现")
        lines.append(
            f"- 文档中的安装命令: {_join(_doc_command_strings(item, 'install'), separator='；')}"
        )
        lines.append(
            f"- 文档中的构建命令: {_join(_doc_command_strings(item, 'build'), separator='；')}"
        )
        lines.append(
            f"- 文档中的测试命令: {_join(_doc_command_strings(item, 'test'), separator='；')}"
        )
        lines.append(
            f"- 文档中的代码检测命令: {_join(_doc_command_strings(item, 'check'), separator='；')}"
        )
        lines.append(
            f"- 文档中的容器命令: {_join(_doc_command_strings(item, 'container'), separator='；')}"
        )
        lines.append(
            f"- 命令推断依据: {_join(item.static.inference_evidence, separator='；')}"
        )

        metrics = [
            ("build", "本地增量构建时间", item.incremental_build, "build"),
            ("check", "本地代码检测时间", item.code_check, "check"),
            ("test", "本地 UT 执行时间", item.unit_test, "test"),
        ]
        for metric_key, label, result, doc_category in metrics:
            lines.append("")
            lines.append(f"### {label}")
            lines.append(f"- 汇总值: `{_metric_duration_text(result)}`")
            lines.append(f"- 命令: `{result.command or 'N/A'}`")
            lines.append(f"- 状态: `{_status_text(result)}`")
            lines.append(f"- 实际探测耗时: `{_duration_text(result.duration_sec)}`")
            if result.status == "ok":
                evidence = _build_metric_success_evidence(
                    item, metric_key, label, result, doc_category
                )
                lines.append("- 成功证据链:")
                for entry in evidence:
                    lines.append(f"  - {entry}")
            else:
                failure = _command_failure_text(result)
                if failure:
                    lines.append(f"- 失败摘要: `{failure}`")
                root_causes = _build_local_metric_root_causes(
                    item, metric_key, label, result, doc_category
                )
                lines.append("- 失败根因分析:")
                for cause in root_causes:
                    lines.append(f"  - [{cause['category']}] {cause['summary']}")
                    for evidence in cause["evidence"]:
                        lines.append(f"    证据: {evidence}")

        lines.append("")
        lines.append("### PR 流水线")
        lines.append(
            f"- PR 指标平台 / 时间窗口: `{item.pr_metrics.remote_platform}` / 最近 `{item.pr_metrics.pr_window_days}` 天"
        )
        lines.append(
            f"- PR 采样数量 / Workflow 数量: `{item.pr_metrics.sampled_pull_count}` / `{item.pr_metrics.workflow_run_count}`"
        )
        lines.append(
            f"- PR 执行时长: 平均 `{_duration_text(item.pr_metrics.average_duration_sec)}` / 中位 `{_duration_text(item.pr_metrics.median_duration_sec)}` / 最近一次 `{_duration_text(item.pr_metrics.latest_duration_sec)}`"
        )
        lines.append(f"- PR 资源消耗: {_resource_text(item)}")
        if item.pr_metrics.average_duration_sec is not None:
            lines.append("- PR 成功证据链:")
            for entry in _build_pr_success_evidence(item.pr_metrics):
                lines.append(f"  - {entry}")
        else:
            lines.append("- PR/资源 N/A 根因分析:")
            for cause in _build_pr_root_causes(item):
                lines.append(f"  - [{cause['category']}] {cause['summary']}")
                for evidence in cause["evidence"]:
                    lines.append(f"    证据: {evidence}")
        lines.append(
            f"- AI 代码检视证据: {_join(item.pr_metrics.ai_review_evidence, separator='；')}"
        )
        lines.append(f"- PR 采集说明: {item.pr_metrics.collection_note or 'N/A'}")
        if item.pr_metrics.workflow_run_evidence:
            lines.append(
                f"- PR Run 证据: {_join(item.pr_metrics.workflow_run_evidence, separator='；')}"
            )

        lines.append("")
        lines.append("### Markdown 改进建议")
        if item.documentation_issues:
            for issue in item.documentation_issues:
                lines.append(f"- {_issue_text(issue)}")
        else:
            lines.append("- N/A")

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
    succeeded_builds = sum(
        1 for item in results if item.incremental_build.status == "ok"
    )
    succeeded_tests = sum(1 for item in results if item.unit_test.status == "ok")
    succeeded_checks = sum(1 for item in results if item.code_check.status == "ok")
    return [
        ("仓库数", str(len(results))),
        ("定义编码风格", str(sum(1 for item in results if item.static.style_defined))),
        (
            "支持代码检测",
            str(sum(1 for item in results if item.static.code_check_supported)),
        ),
        ("构建成功", str(succeeded_builds)),
        ("代码检测成功", str(succeeded_checks)),
        ("UT 成功", str(succeeded_tests)),
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
        return (
            f'<div class="kv"><div class="k">{escape(title)}</div>'
            '<div class="v muted">N/A</div></div>'
        )
    visible = values[:6]
    hidden = values[6:]
    items = "".join(f"<li>{escape(value)}</li>" for value in visible)
    if hidden:
        hidden_items = "".join(f"<li>{escape(value)}</li>" for value in hidden)
        items += (
            f'<details class="list-details"><summary>展开剩余 {len(hidden)} 项</summary>'
            f"<ul>{hidden_items}</ul></details>"
        )
    return (
        f'<div class="kv"><div class="k">{escape(title)}</div>'
        f'<div class="v"><ul>{items}</ul></div></div>'
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
    return (
        f'<span class="status {escape(_html_status_class(result.status))}">'
        f"{escape(_status_text(result))}</span>"
    )


def _render_html_root_causes(causes: list[dict[str, object]]) -> str:
    if not causes:
        return '<div class="callout ok">该指标已成功获取，无需失败根因分析。</div>'
    chunks: list[str] = []
    for cause in causes:
        visible = list(cause["evidence"])[:4]
        hidden = list(cause["evidence"])[4:]
        evidence = "".join(
            f"<li>{escape(str(value))}</li>" for value in cause["evidence"]
        )
        if hidden:
            hidden_items = "".join(f"<li>{escape(str(value))}</li>" for value in hidden)
            evidence = "".join(
                f"<li>{escape(str(value))}</li>" for value in visible
            ) + (
                f'<details class="list-details"><summary>展开更多证据 {len(hidden)} 条</summary>'
                f"<ul>{hidden_items}</ul></details>"
            )
        chunks.append(
            '<div class="callout warn">'
            f"<strong>{escape(str(cause['category']))}</strong>"
            f"<div>{escape(str(cause['summary']))}</div>"
            f"<ul>{evidence}</ul>"
            "</div>"
        )
    return "".join(chunks)


def _render_html_success_evidence(values: list[str]) -> str:
    if not values:
        return '<div class="callout muted">N/A</div>'
    items = "".join(f"<li>{escape(value)}</li>" for value in values)
    return f'<div class="callout ok"><ul>{items}</ul></div>'


def _render_metric_card(
    item: RepoEvaluationResult,
    metric_key: str,
    label: str,
    result: CommandExecutionResult,
    doc_category: str,
) -> str:
    success_evidence = _build_metric_success_evidence(
        item, metric_key, label, result, doc_category
    )
    root_causes = _build_local_metric_root_causes(
        item, metric_key, label, result, doc_category
    )
    return f"""
    <div class="card metric-card">
      <h3>{escape(label)}</h3>
      <div class="kv"><div class="k">汇总值</div><div class="v"><strong>{escape(_metric_duration_text(result))}</strong></div></div>
      <div class="kv"><div class="k">状态</div><div class="v">{_status_badge(result)}</div></div>
      <div class="kv"><div class="k">命令</div><div class="v"><code>{escape(result.command or "N/A")}</code></div></div>
      <div class="kv"><div class="k">实际探测耗时</div><div class="v">{escape(_duration_text(result.duration_sec))}</div></div>
      <div class="kv"><div class="k">失败摘要</div><div class="v">{escape(_command_failure_text(result) or "N/A")}</div></div>
      <div class="kv"><div class="k">成功证据链</div><div class="v">{_render_html_success_evidence(success_evidence)}</div></div>
      <div class="kv"><div class="k">失败根因分析</div><div class="v">{_render_html_root_causes(root_causes)}</div></div>
    </div>
    """


def _render_html_issue_overview(results: list[RepoEvaluationResult]) -> str:
    issue_counter = Counter()
    for item in results:
        issue_counter.update(issue.category for issue in item.documentation_issues)
    if not issue_counter:
        return '<tr><td colspan="2">当前没有识别出 Markdown 与实际执行之间的明显偏差。</td></tr>'
    return "".join(
        f"<tr><td>{escape(category)}</td><td>{count}</td></tr>"
        for category, count in issue_counter.most_common()
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
    pr_causes = _build_pr_root_causes(item)
    pr_evidence = _build_pr_success_evidence(item.pr_metrics)
    rule_items = [
        f"{detail.source}: {detail.count if detail.count is not None else 'N/A'} ({detail.note})"
        for detail in item.static.rule_count_details
    ]
    return f"""
<section class="repo-panel {"active" if index == 0 else ""}" id="repo-panel-{index}">
  <div class="panel-grid">
    <div class="card">
      <h3>基础概览</h3>
      <div class="kv"><div class="k">仓库</div><div class="v">{escape(item.repo)}</div></div>
      <div class="kv"><div class="k">本地路径</div><div class="v"><code>{escape(item.local_path)}</code></div></div>
      <div class="kv"><div class="k">Markdown 扫描文件数</div><div class="v">{item.static.documentation.markdown_files_scanned}</div></div>
      <div class="kv"><div class="k">编码风格</div><div class="v">{escape(_bool_text(item.static.style_defined))}</div></div>
      <div class="kv"><div class="k">代码检测</div><div class="v">{escape(_bool_text(item.static.code_check_supported))}</div></div>
      <div class="kv"><div class="k">自动修复</div><div class="v">{escape(_bool_text(item.static.auto_fix_supported))}</div></div>
      <div class="kv"><div class="k">容器环境</div><div class="v">{escape(_bool_text(item.static.container_environment.defined))} / {escape(_bool_text(item.static.container_environment.setup_supported_locally))} / <code>{escape(item.static.container_environment.preferred_strategy)}</code></div></div>
      <div class="kv"><div class="k">规则数量估算</div><div class="v">{escape(str(item.static.rule_count_estimate or "N/A"))}</div></div>
      <div class="kv"><div class="k">容器准备命令</div><div class="v"><code>{escape(item.static.container_environment.inferred_setup_command or "N/A")}</code></div></div>
      <div class="kv"><div class="k">容器环境说明</div><div class="v">{escape(item.static.container_environment.note or "N/A")}</div></div>
    </div>
    {_render_metric_card(item, "build", "本地增量构建时间", item.incremental_build, "build")}
    {_render_metric_card(item, "check", "本地代码检测时间", item.code_check, "check")}
    {_render_metric_card(item, "test", "本地 UT 执行时间", item.unit_test, "test")}
  </div>
  <div class="panel-grid">
    <div class="card">
      <h3>PR 流水线</h3>
      <div class="kv"><div class="k">平台 / 时间窗口</div><div class="v"><code>{escape(item.pr_metrics.remote_platform)}</code> / 最近 {item.pr_metrics.pr_window_days} 天</div></div>
      <div class="kv"><div class="k">PR 样本 / Workflow 样本</div><div class="v">{item.pr_metrics.sampled_pull_count} / {item.pr_metrics.workflow_run_count}</div></div>
      <div class="kv"><div class="k">平均时长</div><div class="v">{escape(_duration_text(item.pr_metrics.average_duration_sec))}</div></div>
      <div class="kv"><div class="k">中位时长</div><div class="v">{escape(_duration_text(item.pr_metrics.median_duration_sec))}</div></div>
      <div class="kv"><div class="k">最近一次</div><div class="v">{escape(_duration_text(item.pr_metrics.latest_duration_sec))}</div></div>
      <div class="kv"><div class="k">资源消耗</div><div class="v">{escape(_resource_text(item))}</div></div>
      <div class="kv"><div class="k">成功证据链</div><div class="v">{_render_html_success_evidence(pr_evidence)}</div></div>
      <div class="kv"><div class="k">失败根因分析</div><div class="v">{_render_html_root_causes(pr_causes)}</div></div>
      <div class="kv"><div class="k">PR 采集说明</div><div class="v">{escape(item.pr_metrics.collection_note or "N/A")}</div></div>
    </div>
    <div class="card">
      <h3>证据链</h3>
      {_render_html_list("编码风格证据", item.static.style_evidence)}
      {_render_html_list("代码检测证据", item.static.check_tools)}
      {_render_html_list("自动修复证据", item.static.auto_fix_evidence)}
      {_render_html_list("规则统计明细", rule_items)}
      {_render_html_list("容器定义文件", item.static.container_environment.dockerfiles + item.static.container_environment.compose_files + item.static.container_environment.devcontainer_files + item.static.container_environment.reference_files)}
      {_render_html_list("容器镜像线索", item.static.container_environment.base_images + item.static.container_environment.workflow_images)}
      {_render_html_list("容器环境阻塞", item.static.container_environment.setup_blockers)}
      {_render_html_list("文档中的构建命令", _doc_command_strings(item, "build"))}
      {_render_html_list("文档中的测试命令", _doc_command_strings(item, "test"))}
      {_render_html_list("文档中的代码检测命令", _doc_command_strings(item, "check"))}
      {_render_html_list("命令推断依据", item.static.inference_evidence)}
      {_render_html_list("AI 代码检视证据", item.pr_metrics.ai_review_evidence)}
      {_render_html_list("PR Run 证据", item.pr_metrics.workflow_run_evidence)}
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
      --bg: #f6f3ec;
      --panel: #fffdf8;
      --ink: #182220;
      --muted: #5d6a65;
      --accent: #0f6b5a;
      --border: #ded7ca;
      --ok-bg: #ddf7e7;
      --ok-fg: #12633d;
      --warn-bg: #fff1d7;
      --warn-fg: #9b5f07;
      --bad-bg: #fbe7e7;
      --bad-fg: #a02622;
      --neutral-bg: #eef1f5;
      --neutral-fg: #55606b;
      --shadow: 0 18px 40px rgba(27, 34, 32, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at 0 0, rgba(255, 215, 171, 0.7), transparent 26%),
        radial-gradient(circle at 100% 0, rgba(200, 232, 223, 0.7), transparent 32%),
        var(--bg);
    }}
    .page {{ max-width: 1480px; margin: 0 auto; padding: 28px 22px 44px; }}
    .hero {{ padding: 18px 4px 22px; }}
    h1 {{ margin: 0 0 8px; font-size: 36px; line-height: 1.05; letter-spacing: -0.03em; }}
    .subtitle {{ color: var(--muted); font-size: 15px; max-width: 920px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 10px 0 22px; }}
    .metric, .card, table {{ background: var(--panel); border: 1px solid var(--border); border-radius: 18px; box-shadow: var(--shadow); }}
    .metric {{ padding: 18px 18px 16px; }}
    .metric-label {{ color: var(--muted); font-size: 12px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: .06em; }}
    .metric-value {{ font-size: 28px; font-weight: 700; color: var(--accent); }}
    .section {{ margin-top: 22px; }}
    .section-title {{ margin: 0 0 12px; font-size: 21px; }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: #f8f4ea; font-weight: 700; }}
    .repo-tabs {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0 18px; }}
    .repo-tab {{ border: 1px solid var(--border); background: rgba(255,255,255,.72); color: var(--muted); border-radius: 999px; padding: 10px 15px; font-weight: 700; cursor: pointer; transition: 140ms ease; }}
    .repo-tab.active {{ background: linear-gradient(135deg, #165f52, #0f493f); color: #fff; border-color: transparent; }}
    .repo-panel {{ display: none; }}
    .repo-panel.active {{ display: block; animation: fadeIn .18s ease; }}
    .panel-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; margin-bottom: 14px; }}
    .card {{ padding: 18px 18px 10px; }}
    .card h3 {{ margin: 0 0 14px; font-size: 18px; }}
    .kv {{ display: grid; grid-template-columns: 150px 1fr; gap: 10px; padding: 9px 0; border-top: 1px solid rgba(222, 215, 202, 0.7); }}
    .kv:first-of-type {{ border-top: 0; }}
    .k {{ color: var(--muted); font-size: 13px; }}
    .v {{ min-width: 0; word-break: break-word; }}
    .muted {{ color: var(--muted); }}
    ul {{ margin: 6px 0 0 18px; padding: 0; }}
    li {{ margin-bottom: 6px; }}
    code {{ font-family: "Cascadia Code", "Consolas", monospace; background: #f3eee4; border-radius: 6px; padding: 2px 6px; font-size: 12px; }}
    .status {{ display: inline-flex; align-items: center; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .status.ok {{ background: var(--ok-bg); color: var(--ok-fg); }}
    .status.failed, .status.error {{ background: var(--bad-bg); color: var(--bad-fg); }}
    .status.timeout {{ background: var(--warn-bg); color: var(--warn-fg); }}
    .status.disabled {{ background: var(--neutral-bg); color: var(--neutral-fg); }}
    .callout {{ border-radius: 12px; padding: 12px 14px; border: 1px solid transparent; }}
    .callout ul {{ margin-top: 8px; }}
    .callout.ok {{ background: rgba(221, 247, 231, 0.7); color: var(--ok-fg); border-color: rgba(18, 99, 61, 0.12); }}
    .callout.warn {{ background: rgba(255, 241, 215, 0.75); color: #6d4a11; border-color: rgba(155, 95, 7, 0.14); margin-bottom: 10px; }}
    .callout.muted {{ background: rgba(238, 241, 245, 0.78); color: var(--neutral-fg); border-color: rgba(85, 96, 107, 0.12); }}
    .metric-card {{ background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(250,247,241,.94)); }}
    .list-details {{ margin-top: 8px; }}
    .list-details summary {{ cursor: pointer; color: var(--accent); font-weight: 700; }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @media (max-width: 920px) {{
      .page {{ padding: 18px 12px 30px; }}
      h1 {{ font-size: 30px; }}
      .kv {{ grid-template-columns: 1fr; gap: 4px; }}
      th, td {{ font-size: 13px; padding: 10px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <h1>开源代码仓开发体验评估报告</h1>
      <div class="subtitle">聚焦本地构建、代码检测、UT、容器环境与 PR 流水线。对于失败项和 N/A，报告会给出结构化根因分类；对于成功项，报告会展示证据链，帮助判断时间数字是否可信。</div>
    </div>
    <div class="metrics">{metrics_html}</div>
    <section class="section">
      <h2 class="section-title">仓库汇总</h2>
      <table>
        <thead>
          <tr>
            <th>仓库</th><th>编码风格</th><th>代码检测</th><th>容器定义</th><th>容器可搭建</th><th>构建时间</th><th>代码检测时间</th><th>UT 时间</th><th>规则数</th><th>自动修复</th><th>AI 代码检视</th><th>PR 平均时长</th><th>PR 资源</th>
          </tr>
        </thead>
        <tbody>{_render_html_summary_table(results)}</tbody>
      </table>
    </section>
    <section class="section">
      <h2 class="section-title">Markdown 改进建议总览</h2>
      <table>
        <thead><tr><th>分类</th><th>数量</th></tr></thead>
        <tbody>{_render_html_issue_overview(results)}</tbody>
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
