from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import load_config
from .contrib_rules import load_contributing_excerpt
from .git_ops import checkout_branch, commit_all, ensure_repo, has_changes, push_branch
from .github_api import GitHubClient
from .models import AppConfig, Issue, RepoPolicy
from .quality import run_quality_gates
from .state import AgentStateStore


@dataclass
class RunResult:
    scanned: int = 0
    attempted: int = 0
    submitted: int = 0
    skipped: int = 0


class FixerAgent:
    def __init__(self, cfg: AppConfig, dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.gh = GitHubClient()
        me = self.gh.current_user()
        self.login = me["login"]
        self.workspace = Path(cfg.workspace_root).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state = AgentStateStore(self.workspace / ".agent-state.json")
        self.project_src = Path(__file__).resolve().parents[1]

    def run_once(
        self, max_prs: int | None = None, repo_allowlist: set[str] | None = None
    ) -> RunResult:
        target = max_prs or self.cfg.daily_target_prs
        result = RunResult()
        for repo in self.cfg.repos:
            if repo_allowlist and repo.name not in repo_allowlist:
                continue
            if result.submitted >= target:
                break
            repo_issues = self.gh.list_open_issues(
                repo.name, repo.labels_any, self.cfg.default_max_issue_scan
            )
            for issue in repo_issues:
                if result.submitted >= target:
                    break
                result.scanned += 1
                if issue.is_pull_request:
                    result.skipped += 1
                    continue
                if not self.state.should_attempt(
                    repo.name, issue.number, self.cfg.attempt_cooldown_hours
                ):
                    result.skipped += 1
                    continue
                ok = self._try_issue(repo, issue)
                result.attempted += 1
                if ok:
                    result.submitted += 1
                    self.state.mark_submitted(repo.name, issue.number)
                else:
                    result.skipped += 1
                    self.state.mark_failed(repo.name, issue.number)
        return result

    def _try_issue(self, repo: RepoPolicy, issue: Issue) -> bool:
        try:
            local_dir = self.workspace / f"{repo.name.replace('/', '__')}"
            fork = self.gh.ensure_fork(repo.name)
            clone_url = fork["clone_url"]
            ensure_repo(local_dir, clone_url)

            base_branch = self.gh.get_default_branch(repo.name)
            safe_suffix = str(issue.number)
            branch = f"{repo.branch_prefix}/{safe_suffix}"
            checkout_branch(local_dir, base_branch, branch)

            contributing = load_contributing_excerpt(self.gh, repo.name)
            context_path = local_dir / ".ai-agent-context.json"
            context_path.write_text(
                json.dumps(
                    {
                        "repo": repo.name,
                        "issue": {
                            "number": issue.number,
                            "title": issue.title,
                            "body": issue.body,
                            "labels": issue.labels,
                            "url": issue.html_url,
                            "type": issue.issue_type,
                        },
                        "contributing_excerpt": contributing,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            cmd = repo.fix_command.format(
                issue_number=issue.number,
                repo=repo.name,
                issue_type=issue.issue_type,
                title=issue.title.replace('"', "'"),
                context_path=str(context_path.name),
            )
            fixed = subprocess.run(
                cmd,
                cwd=str(local_dir),
                shell=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=max(60, repo.fix_timeout_sec),
                env={
                    **dict(os.environ),
                    "PYTHONPATH": str(self.project_src),
                },
            )
            log_dir = local_dir / ".ai-agent"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / f"fixer-{issue.number}.log").write_text(
                "\n".join(
                    [
                        f"$ {cmd}",
                        "",
                        "=== STDOUT ===",
                        fixed.stdout,
                        "",
                        "=== STDERR ===",
                        fixed.stderr,
                        "",
                        f"exit_code={fixed.returncode}",
                    ]
                ),
                encoding="utf-8",
            )
            if fixed.returncode != 0:
                return False
            if not has_changes(local_dir):
                return False

            passed, _logs = run_quality_gates(local_dir, repo.checks)
            if not passed:
                return False

            commit_msg = repo.commit_template.format(
                issue_number=issue.number,
                title=issue.title[:72],
            )
            pr_title = repo.pr_title_template[issue.issue_type].format(
                title=issue.title[:100]
            )
            pr_body = (
                f"Auto-generated fix for #{issue.number}.\n\n"
                f"- Source issue: {issue.html_url}\n"
                f"- Type: {issue.issue_type}\n"
                f"- Quality gates: passed\n"
            )

            if self.dry_run:
                return True

            commit_all(local_dir, commit_msg)
            push_branch(local_dir, branch)
            self.gh.create_pull_request(
                upstream_repo=repo.name,
                base_branch=base_branch,
                head_ref=f"{self.login}:{branch}",
                title=pr_title,
                body=pr_body,
            )
            return True
        except Exception:
            return False
