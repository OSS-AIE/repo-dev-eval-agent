from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "tools" / "ai_pr_review.py"
    spec = importlib.util.spec_from_file_location("ai_pr_review", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_openai_output_text_prefers_top_level_field():
    module = _load_module()
    payload = {"output_text": "review summary"}

    assert module._extract_openai_output_text(payload) == "review summary"


def test_extract_openai_output_text_falls_back_to_output_items():
    module = _load_module()
    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "line 1"},
                    {"type": "output_text", "text": "line 2"},
                ]
            }
        ]
    }

    assert module._extract_openai_output_text(payload) == "line 1\nline 2"


def test_extract_gemini_output_text_reads_candidate_parts():
    module = _load_module()
    payload = {
        "candidates": [
            {"content": {"parts": [{"text": "line 1"}, {"text": "line 2"}]}}
        ]
    }

    assert module._extract_gemini_output_text(payload) == "line 1\nline 2"


def test_required_api_key_uses_gemini_fallback(monkeypatch):
    module = _load_module()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")

    assert module._required_api_key("gemini") == "google-key"


def test_comment_marker_and_heading_are_configurable(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("AI_REVIEW_MARKER", "<!-- marker -->")
    monkeypatch.setenv("AI_REVIEW_HEADING", "Gemini review")

    assert module._comment_marker() == "<!-- marker -->"
    assert module._comment_heading() == "Gemini review"


def test_build_missing_key_comment_body_contains_settings_guidance(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "OSS-AIE/repo-dev-eval-agent")

    body = module._build_missing_key_comment_body(
        "openai",
        "https://github.com/OSS-AIE/repo-dev-eval-agent/pull/2",
    )

    assert "OPENAI_API_KEY" in body
    assert "/settings/secrets/actions" in body
    assert "状态: 已跳过" in body


def test_request_ai_review_routes_to_provider(monkeypatch):
    module = _load_module()
    context = module.GitHubContext(
        repo="OSS-AIE/repo-dev-eval-agent",
        pr_number=1,
        api_url="https://api.github.com",
        server_url="https://github.com",
        token="token",
    )
    snapshot = {"pr": {}, "files": [], "diff": ""}
    monkeypatch.setenv("AI_REVIEW_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")

    def fake_gemini_review(_snapshot, _context):
        assert _snapshot is snapshot
        assert _context is context
        return "gemini review"

    monkeypatch.setattr(module, "_request_gemini_review", fake_gemini_review)

    assert module._request_ai_review(snapshot, context) == "gemini review"


def test_main_skips_when_provider_key_missing(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setenv("AI_REVIEW_PROVIDER", "gemini")
    monkeypatch.setenv("GITHUB_REPOSITORY", "OSS-AIE/repo-dev-eval-agent")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("PR_NUMBER", "12")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        module,
        "_fetch_pr_snapshot",
        lambda context: {
            "pr": {"html_url": "https://example.invalid/pr/12"},
            "files": [],
            "diff": "",
        },
    )
    published: dict[str, str] = {}

    def fake_publish(context, body):
        published["body"] = body

    monkeypatch.setattr(module, "_publish_comment", fake_publish)

    assert module.main() == 0
    assert "gemini API key is not configured" in capsys.readouterr().out
    assert "GEMINI_API_KEY or GOOGLE_API_KEY" in published["body"]
