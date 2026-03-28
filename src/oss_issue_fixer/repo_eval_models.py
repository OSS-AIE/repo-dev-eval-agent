from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RunnerCapacity:
    vcpus: int | None = None
    npu_cards: int | None = None


@dataclass
class LocalEvalConfig:
    setup_command: str = ""
    command_prefix: str = ""
    build_command: str = ""
    incremental_build_command: str = ""
    unit_test_command: str = ""
    code_check_command: str = ""
    runner: str = "host"
    wsl_distro: str = ""
    wsl_workspace_root: str = ""
    prefer_wsl_native_workspace: bool = True
    refresh_local_repo: bool = True
    documentation_refs: list[str] = field(default_factory=list)
    timeout_sec: int = 1800


@dataclass
class RemoteEvalConfig:
    workflow_events: list[str] = field(default_factory=lambda: ["pull_request"])
    runner_capacity_overrides: dict[str, RunnerCapacity] = field(default_factory=dict)
    pr_window_days: int = 30
    github_token_env: str = "GITHUB_TOKEN"
    gitcode_token_env: str = "GITCODE_TOKEN"
    ai_review_author_markers: list[str] = field(default_factory=list)


GitHubEvalConfig = RemoteEvalConfig


@dataclass
class AIEvalConfig:
    enabled: bool = False
    provider: str = ""
    command: str = ""
    command_template: str = ""
    model: str = ""


@dataclass
class RepoEvalPolicy:
    name: str
    local_path: str = ""
    clone_url: str = ""
    local: LocalEvalConfig = field(default_factory=LocalEvalConfig)
    github: RemoteEvalConfig = field(default_factory=RemoteEvalConfig)
    ai: AIEvalConfig = field(default_factory=AIEvalConfig)


@dataclass
class RepoEvalAppConfig:
    workspace_root: str = ".work/eval"
    report_root: str = "reports/eval"
    recent_pr_limit: int = 10
    recent_review_pr_limit: int = 10
    default_timeout_sec: int = 1800
    enable_command_inference: bool = True
    enable_local_commands: bool = False
    repos: list[RepoEvalPolicy] = field(default_factory=list)


@dataclass
class RuleCountDetail:
    source: str
    count: int | None
    note: str = ""


@dataclass
class ContainerRuntimeProbe:
    engine: str = ""
    cli_available: bool = False
    daemon_available: bool = False
    server_version: str = ""
    nvidia_runtime_available: bool = False
    evidence: list[str] = field(default_factory=list)


@dataclass
class ContainerEnvironmentAssessment:
    defined: bool = False
    runnable_definition_present: bool = False
    preferred_strategy: str = "host"
    dockerfiles: list[str] = field(default_factory=list)
    compose_files: list[str] = field(default_factory=list)
    devcontainer_files: list[str] = field(default_factory=list)
    reference_files: list[str] = field(default_factory=list)
    base_images: list[str] = field(default_factory=list)
    workflow_images: list[str] = field(default_factory=list)
    requires_gpu: bool = False
    setup_supported_locally: bool = False
    setup_evidence: list[str] = field(default_factory=list)
    setup_blockers: list[str] = field(default_factory=list)
    inferred_setup_command: str = ""
    runtime: ContainerRuntimeProbe = field(default_factory=ContainerRuntimeProbe)
    note: str = ""


@dataclass
class DocumentationCommand:
    source_file: str
    category: str
    command: str


@dataclass
class DocumentationAssessment:
    markdown_files_scanned: int = 0
    relevant_files: list[str] = field(default_factory=list)
    commands: list[DocumentationCommand] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class DocumentationIssue:
    category: str
    root_cause: str
    severity: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class StaticAnalysisResult:
    style_defined: bool = False
    style_evidence: list[str] = field(default_factory=list)
    code_check_supported: bool = False
    check_tools: list[str] = field(default_factory=list)
    rule_count_estimate: int = 0
    rule_count_details: list[RuleCountDetail] = field(default_factory=list)
    auto_fix_supported: bool = False
    auto_fix_evidence: list[str] = field(default_factory=list)
    ai_review_signals: list[str] = field(default_factory=list)
    inferred_build_command: str = ""
    inferred_unit_test_command: str = ""
    inferred_code_check_command: str = ""
    inference_evidence: list[str] = field(default_factory=list)
    container_environment: ContainerEnvironmentAssessment = field(
        default_factory=ContainerEnvironmentAssessment
    )
    documentation: DocumentationAssessment = field(
        default_factory=DocumentationAssessment
    )


@dataclass
class CommandExecutionResult:
    status: str = "not_configured"
    command: str = ""
    duration_sec: float | None = None
    returncode: int | None = None
    setup_command: str = ""
    setup_status: str = ""
    setup_duration_sec: float | None = None
    setup_stdout_excerpt: str = ""
    setup_stderr_excerpt: str = ""
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""


@dataclass
class PullRequestMetrics:
    remote_platform: str = "github"
    pr_window_days: int = 30
    window_start: str = ""
    window_end: str = ""
    sampled_pull_count: int = 0
    workflow_run_count: int = 0
    latest_duration_sec: float | None = None
    median_duration_sec: float | None = None
    average_duration_sec: float | None = None
    estimated_cpu_core_minutes: float | None = None
    estimated_npu_card_minutes: float | None = None
    actual_cpu_seconds: float | None = None
    actual_npu_seconds: float | None = None
    ai_review_supported: bool = False
    ai_review_evidence: list[str] = field(default_factory=list)
    workflow_run_evidence: list[str] = field(default_factory=list)
    collection_note: str = ""


@dataclass
class AISummary:
    provider: str = ""
    status: str = "disabled"
    summary: str = ""
    command: str = ""
    stderr_excerpt: str = ""


@dataclass
class RepoEvaluationResult:
    repo: str
    local_path: str
    static: StaticAnalysisResult
    incremental_build: CommandExecutionResult
    unit_test: CommandExecutionResult
    code_check: CommandExecutionResult
    pr_metrics: PullRequestMetrics
    documentation_issues: list[DocumentationIssue] = field(default_factory=list)
    ai_summary: AISummary = field(default_factory=AISummary)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
