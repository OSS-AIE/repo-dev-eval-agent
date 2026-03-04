from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--type", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    # Replace this stub with your real repair pipeline (LLM/tool-use/tests).
    out_dir = Path(".ai-agent")
    out_dir.mkdir(parents=True, exist_ok=True)
    marker = out_dir / f"issue-{args.issue}.md"
    marker.write_text(
        "\n".join(
            [
                f"# Auto Fix Plan for {args.repo}#{args.issue}",
                f"- Type: {args.type}",
                f"- Title: {args.title}",
                "- NOTE: replace stub_fixer with real code patcher before production.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
