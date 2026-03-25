from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "tools" / "ai_pr_review.py"
    )
    spec = importlib.util.spec_from_file_location("ai_pr_review", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_output_text_prefers_top_level_field():
    module = _load_module()
    payload = {"output_text": "review summary"}

    assert module._extract_output_text(payload) == "review summary"


def test_extract_output_text_falls_back_to_output_items():
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

    assert module._extract_output_text(payload) == "line 1\nline 2"
