from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .repo_eval_models import AISummary, RepoEvalPolicy, RepoEvaluationResult


def _default_command_template(provider: str) -> str:
    lowered = provider.lower()
    if lowered in {"codex", "openai-codex"}:
        return '"{command}" exec -C "{cwd}" -'
    if lowered == "opencode":
        return '"{command}" run -C "{cwd}" -'
    return ""


def _command_exists(name: str) -> bool:
    if not name:
        return False
    if Path(name).exists():
        return True
    return bool(shutil.which(name))


def _build_prompt(result: RepoEvaluationResult) -> str:
    payload = {
        "repo": result.repo,
        "static": result.static.__dict__,
        "incremental_build": result.incremental_build.__dict__,
        "unit_test": result.unit_test.__dict__,
        "code_check": result.code_check.__dict__,
        "pr_metrics": result.pr_metrics.__dict__,
        "documentation_issues": [item.__dict__ for item in result.documentation_issues],
        "errors": result.errors,
    }
    return (
        "You are analyzing repository engineering efficiency.\n"
        "Given the JSON facts below, write a concise Chinese summary with:\n"
        "1. strongest signals\n"
        "2. biggest DX / quality gap\n"
        "3. next recommended improvement\n"
        "Keep it under 8 lines.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def summarize_with_ai(
    repo_path: Path,
    policy: RepoEvalPolicy,
    result: RepoEvaluationResult,
    disable_ai: bool = False,
) -> AISummary:
    if disable_ai or not policy.ai.enabled:
        return AISummary(provider=policy.ai.provider, status="disabled")

    provider = (policy.ai.provider or "").strip().lower()
    command = (policy.ai.command or "").strip()
    if not command:
        if provider in {"codex", "openai-codex"}:
            command = "codex.cmd"
        elif provider == "opencode":
            command = "opencode"

    if not _command_exists(command):
        return AISummary(
            provider=provider,
            status="unavailable",
            command=command,
            stderr_excerpt="command not found in PATH",
        )

    template = policy.ai.command_template or _default_command_template(provider)
    if not template:
        return AISummary(
            provider=provider,
            status="unsupported_provider",
            command=command,
            stderr_excerpt=f"unsupported provider: {provider}",
        )

    formatted = template.format(
        command=command,
        cwd=str(repo_path),
        model=policy.ai.model,
    )
    prompt = _build_prompt(result)
    proc = subprocess.run(
        formatted,
        cwd=str(repo_path),
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=prompt,
        capture_output=True,
        check=False,
        timeout=300,
    )
    summary = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return AISummary(
            provider=provider,
            status="failed",
            command=formatted,
            stderr_excerpt=(proc.stderr or "")[:500],
        )
    return AISummary(
        provider=provider,
        status="ok",
        command=formatted,
        summary=summary[:4000],
        stderr_excerpt=(proc.stderr or "")[:500],
    )
