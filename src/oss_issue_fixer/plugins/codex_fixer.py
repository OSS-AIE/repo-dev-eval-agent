from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_codex_command() -> list[str]:
    for candidate in ("codex.cmd", "codex"):
        path = shutil.which(candidate)
        if path:
            return [path]
    raise RuntimeError("Cannot find codex CLI in PATH. Install Codex CLI first.")


def _build_prompt(context: dict) -> str:
    issue = context.get("issue", {})
    issue_body = (issue.get("body") or "").strip()
    if not issue_body:
        issue_body = "(empty issue body)"
    contributing_excerpt = (context.get("contributing_excerpt") or "").strip()
    if not contributing_excerpt:
        contributing_excerpt = "(no CONTRIBUTING excerpt available)"
    prompt = f"""
You are fixing a GitHub issue in this repository.

Issue metadata:
- Number: {issue.get("number")}
- Title: {issue.get("title")}
- URL: {issue.get("url")}
- Type: {issue.get("type")}
- Labels: {issue.get("labels")}

Issue body:
{issue_body}

CONTRIBUTING excerpt:
{contributing_excerpt}

Execution rules:
1. Make the minimum safe code changes to address the issue.
2. Add or update tests if a regression test is appropriate.
3. Do not commit or push.
4. Keep code style consistent with the repository.
5. At the end, print a short summary of changed files and why.
""".strip()
    return prompt


def _write_stub_patch(issue_number: int, repo: str, issue_type: str, title: str) -> None:
    out_dir = Path(".ai-agent")
    out_dir.mkdir(parents=True, exist_ok=True)
    marker = out_dir / f"issue-{issue_number}.md"
    marker.write_text(
        "\n".join(
            [
                f"# Offline Fix Plan for {repo}#{issue_number}",
                f"- Type: {issue_type}",
                f"- Title: {title}",
                "- NOTE: Codex/API unavailable, fallback stub generated for local pipeline validation.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", default=".ai-agent-context.json")
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--type", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    context_path = Path(args.context)
    if not context_path.exists():
        raise RuntimeError(f"Context file not found: {context_path}")
    context = json.loads(context_path.read_text(encoding="utf-8"))
    prompt = _build_prompt(context)

    codex_cmd = _resolve_codex_command()
    cmd = codex_cmd + [
        "exec",
        "--full-auto",
        "-C",
        str(Path.cwd()),
        prompt,
    ]
    model = os.getenv("OPENAI_MODEL", "").strip()
    if model:
        cmd.extend(["-m", model])

    timeout_sec = int(os.getenv("CODEX_FIXER_TIMEOUT_SEC", "1800"))
    try:
        run = subprocess.run(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout_sec,
        )
    except Exception as exc:
        if os.getenv("ALLOW_STUB_FALLBACK", "0") == "1":
            _write_stub_patch(args.issue, args.repo, args.type, args.title)
            return
        raise RuntimeError(f"failed to invoke codex: {exc}") from exc

    out_dir = Path(".ai-agent")
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"codex-issue-{args.issue}.log"
    log_path.write_text(
        "\n".join(
            [
                "$ " + " ".join(cmd),
                "",
                "=== STDOUT ===",
                run.stdout or "",
                "",
                "=== STDERR ===",
                run.stderr or "",
                "",
                f"exit_code={run.returncode}",
            ]
        ),
        encoding="utf-8",
    )

    if run.returncode != 0:
        if os.getenv("ALLOW_STUB_FALLBACK", "0") == "1":
            _write_stub_patch(args.issue, args.repo, args.type, args.title)
            return
        print(
            f"codex_fixer failed for {args.repo}#{args.issue}, "
            f"see {log_path}",
            file=sys.stderr,
        )
        raise SystemExit(run.returncode)


if __name__ == "__main__":
    main()
