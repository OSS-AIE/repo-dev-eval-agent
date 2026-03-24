from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .agent import FixerAgent
from .config import load_config
from .repo_eval_agent import RepoEvalAgent
from .repo_eval_config import load_repo_eval_config
from .repo_eval_models import (
    AIEvalConfig,
    LocalEvalConfig,
    RepoEvalAppConfig,
    RepoEvalPolicy,
    RemoteEvalConfig,
)
from .repo_eval_report import render_repo_eval_markdown
from .scheduler import run_daily
from .smoke import run_local_smoke


def _git_remote_origin(repo_path: Path) -> str:
    proc = subprocess.run(
        "git remote get-url origin",
        cwd=str(repo_path),
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=10,
    )
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _repo_name_from_remote(remote_url: str) -> tuple[str, str]:
    if remote_url.startswith("git@") and ":" in remote_url:
        prefix, repo_part = remote_url.split(":", 1)
        host = prefix.split("@", 1)[-1].lower()
        parts = [part for part in repo_part.strip("/").split("/") if part]
        if len(parts) >= 2:
            owner = parts[0]
            repo = parts[1].removesuffix(".git")
            return f"{owner}/{repo}", host
    parsed = urlparse(remote_url)
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) >= 2:
        owner = parts[0]
        repo = parts[1].removesuffix(".git")
        return f"{owner}/{repo}", host
    return "", host


def _policy_from_repo_input(
    raw: str,
    *,
    local_runner: str,
    local_wsl_distro: str,
    remote_cfg: RemoteEvalConfig,
    ai_cfg: AIEvalConfig,
) -> RepoEvalPolicy:
    candidate = Path(raw)
    if candidate.exists():
        local_path = str(candidate.resolve())
        origin = _git_remote_origin(candidate.resolve())
        name, host = _repo_name_from_remote(origin)
        if not name:
            name = candidate.resolve().name
        clone_url = origin
        if not clone_url and "/" in name and "gitcode" in host:
            clone_url = f"https://gitcode.com/{name}.git"
        elif not clone_url and "/" in name:
            clone_url = f"https://github.com/{name}.git"
        return RepoEvalPolicy(
            name=name,
            local_path=local_path,
            clone_url=clone_url,
            local=LocalEvalConfig(
                runner=local_runner,
                wsl_distro=local_wsl_distro,
            ),
            github=remote_cfg,
            ai=ai_cfg,
        )

    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"unsupported repo url: {raw}")
        owner = parts[0]
        repo = parts[1].removesuffix(".git")
        clone_url = raw if raw.endswith(".git") else raw.rstrip("/") + ".git"
        return RepoEvalPolicy(
            name=f"{owner}/{repo}",
            clone_url=clone_url,
            local=LocalEvalConfig(
                runner=local_runner,
                wsl_distro=local_wsl_distro,
            ),
            github=remote_cfg,
            ai=ai_cfg,
        )

    if raw.count("/") == 1 and not raw.startswith("."):
        return RepoEvalPolicy(
            name=raw,
            clone_url=f"https://github.com/{raw}.git",
            local=LocalEvalConfig(
                runner=local_runner,
                wsl_distro=local_wsl_distro,
            ),
            github=remote_cfg,
            ai=ai_cfg,
        )

    raise ValueError(
        f"unsupported repo input: {raw}. expected local path, repo URL, or owner/repo"
    )


def _write_eval_reports(
    *,
    results,
    report_md_path: str,
    report_json_path: str,
) -> None:
    report_md = render_repo_eval_markdown(results)
    print(report_md)

    if report_md_path:
        out_md = Path(report_md_path)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(report_md, encoding="utf-8")
        print(f"markdown report written: {out_md.resolve()}")

    if report_json_path:
        out_json = Path(report_json_path)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps(
                [item.to_dict() for item in results],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"json report written: {out_json.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="oss-fixer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    once = sub.add_parser("run-once")
    once.add_argument("--config", required=True)
    once.add_argument("--max-prs", type=int, default=None)
    once.add_argument("--dry-run", action="store_true")
    once.add_argument("--repo", action="append", default=[])
    once.add_argument("--result-json", default="")

    daily = sub.add_parser("run-daily")
    daily.add_argument("--config", required=True)
    daily.add_argument("--dry-run", action="store_true")

    smoke = sub.add_parser("run-local-smoke")
    smoke.add_argument("--config", required=True)
    smoke.add_argument("--repo", required=True)
    smoke.add_argument("--issue-number", type=int, default=999999)
    smoke.add_argument("--issue-title", default="Local smoke test issue")
    smoke.add_argument("--issue-body", default="Validate local end-to-end fixer flow.")
    smoke.add_argument("--skip-checks", action="store_true")

    evaluate = sub.add_parser("evaluate-repos")
    evaluate.add_argument("--config", required=True)
    evaluate.add_argument("--repo", action="append", default=[])
    evaluate.add_argument("--report-md", default="")
    evaluate.add_argument("--report-json", default="")
    evaluate.add_argument("--enable-local-commands", action="store_true")
    evaluate.add_argument("--disable-local-commands", action="store_true")
    evaluate.add_argument("--no-ai", action="store_true")

    assess = sub.add_parser("assess-repos")
    assess.add_argument("--repo", action="append", required=True, default=[])
    assess.add_argument("--workspace-root", default=".work/eval")
    assess.add_argument("--report-root", default="reports/eval")
    assess.add_argument("--report-prefix", default="")
    assess.add_argument("--report-md", default="")
    assess.add_argument("--report-json", default="")
    assess.add_argument("--recent-pr-limit", type=int, default=20)
    assess.add_argument("--recent-review-pr-limit", type=int, default=20)
    assess.add_argument("--pr-window-days", type=int, default=30)
    assess.add_argument("--default-timeout-sec", type=int, default=1800)
    assess.add_argument("--local-runner", choices=["host", "wsl"], default="host")
    assess.add_argument("--wsl-distro", default="")
    assess.add_argument("--enable-command-inference", action="store_true")
    assess.add_argument("--disable-command-inference", action="store_true")
    assess.add_argument(
        "--enable-local-commands",
        dest="enable_local_commands",
        action="store_true",
    )
    assess.add_argument(
        "--disable-local-commands",
        dest="enable_local_commands",
        action="store_false",
    )
    assess.set_defaults(enable_local_commands=True)
    assess.add_argument("--enable-ai", action="store_true")
    assess.add_argument("--ai-provider", default="codex")
    assess.add_argument("--ai-command", default="")
    assess.add_argument("--ai-command-template", default="")
    assess.add_argument("--ai-model", default="")
    assess.add_argument("--github-token-env", default="GITHUB_TOKEN")
    assess.add_argument("--gitcode-token-env", default="GITCODE_TOKEN")
    assess.add_argument("--ai-review-marker", action="append", default=[])

    args = parser.parse_args()
    if args.cmd == "evaluate-repos":
        cfg = load_repo_eval_config(args.config)
        agent = RepoEvalAgent(
            cfg=cfg,
            enable_local_commands_override=(
                True
                if args.enable_local_commands
                else False if args.disable_local_commands
                else None
            ),
            disable_ai=args.no_ai,
        )
        allow = set(args.repo) if args.repo else None
        results = agent.run(repo_allowlist=allow)
        _write_eval_reports(
            results=results,
            report_md_path=args.report_md,
            report_json_path=args.report_json,
        )
        return

    if args.cmd == "assess-repos":
        remote_cfg = RemoteEvalConfig(
            workflow_events=["pull_request", "pull_request_target"],
            pr_window_days=args.pr_window_days,
            github_token_env=args.github_token_env,
            gitcode_token_env=args.gitcode_token_env,
            ai_review_author_markers=list(args.ai_review_marker or []),
        )
        ai_cfg = AIEvalConfig(
            enabled=bool(args.enable_ai),
            provider=args.ai_provider,
            command=args.ai_command,
            command_template=args.ai_command_template,
            model=args.ai_model,
        )
        repos = [
            _policy_from_repo_input(
                raw,
                local_runner=args.local_runner,
                local_wsl_distro=args.wsl_distro,
                remote_cfg=remote_cfg,
                ai_cfg=ai_cfg,
            )
            for raw in args.repo
        ]
        cfg = RepoEvalAppConfig(
            workspace_root=args.workspace_root,
            report_root=args.report_root,
            recent_pr_limit=args.recent_pr_limit,
            recent_review_pr_limit=args.recent_review_pr_limit,
            default_timeout_sec=args.default_timeout_sec,
            enable_command_inference=(
                False if args.disable_command_inference else True
            ),
            enable_local_commands=bool(args.enable_local_commands),
            repos=repos,
        )
        agent = RepoEvalAgent(
            cfg=cfg,
            enable_local_commands_override=args.enable_local_commands,
            disable_ai=not args.enable_ai,
        )
        results = agent.run()
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = args.report_prefix or f"repo-eval-{timestamp}"
        report_md = args.report_md or str(Path(args.report_root) / f"{prefix}.md")
        report_json = args.report_json or str(Path(args.report_root) / f"{prefix}.json")
        _write_eval_reports(
            results=results,
            report_md_path=report_md,
            report_json_path=report_json,
        )
        return

    cfg = load_config(args.config)
    if args.cmd == "run-local-smoke":
        res = run_local_smoke(
            cfg=cfg,
            repo_name=args.repo,
            issue_number=args.issue_number,
            issue_title=args.issue_title,
            issue_body=args.issue_body,
            skip_checks=args.skip_checks,
        )
        print(
            "local-smoke done: "
            f"repo={res.repo} issue={res.issue_number} changed={res.changed} "
            f"checks_passed={res.checks_passed} branch={res.branch} worktree={res.worktree}"
        )
        return

    try:
        agent = FixerAgent(cfg, dry_run=args.dry_run)
    except Exception as exc:
        print(f"failed to initialize agent: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if args.cmd == "run-once":
        allow = set(args.repo) if args.repo else None
        res = agent.run_once(args.max_prs, repo_allowlist=allow)
        print(
            f"run-once done: scanned={res.scanned}, attempted={res.attempted}, "
            f"submitted={res.submitted}, skipped={res.skipped}"
        )
        if args.result_json:
            payload = {
                "scanned": res.scanned,
                "attempted": res.attempted,
                "submitted": res.submitted,
                "skipped": res.skipped,
            }
            Path(args.result_json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return
    run_daily(agent)


if __name__ == "__main__":
    main()
