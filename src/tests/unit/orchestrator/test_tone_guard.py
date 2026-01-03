import json
import pytest

import src.orchestrator.nodes.tone_guard as tone_guard
from src.orchestrator.nodes.tone_guard import lint_tone, tone_linter_node


def test_linter_matches_word_boundary_case_insensitive(monkeypatch, tmp_path):
    # Configure a minimal neutral_tone.yaml
    cfg = tmp_path / "neutral_tone.yaml"
    cfg.write_text(
        """
terms:
  - word: revolutionary
    replacement: balanced
    severity: fail
    category: hype
"""
    )
    # Patch at the source module where _load_patterns actually calls load_neutral_tone_yaml
    monkeypatch.setattr("src.orchestrator.tone_guard.load_neutral_tone_yaml", lambda: {"terms": [{"word": "revolutionary", "replacement": "balanced", "severity": "fail"}]})
    tone_guard._PATTERN, tone_guard._REPLACEMENTS, tone_guard._SEVERITIES, tone_guard._CATEGORIES = tone_guard._load_patterns()

    text = "Revolutionary findings. A revolutionary idea. Not inrevolutionary."
    findings = lint_tone(text)
    assert len(findings) == 2
    words = {f["word"].lower() for f in findings}
    assert words == {"revolutionary"}


def test_exploratory_warns_does_not_fail(monkeypatch):
    # Patch at the source module where tone_linter_node actually calls lint_tone
    findings = [{"word": "revolutionary", "severity": "warn", "location": {"start": 0, "end": 5}, "suggestion": "balanced", "category": None}]
    monkeypatch.setattr("src.orchestrator.tone_guard.lint_tone", lambda text: findings)
    state = {"synthesis": "revolutionary", "rigor_level": "exploratory", "jobId": "j1", "threadId": "j1"}
    result = tone_linter_node(state)
    assert "tone_findings" in result
    assert result.get("tone_flags"), f"Expected tone_flags to be non-empty, got: {result.get('tone_flags')}"
    assert len(result.get("tone_flags", [])) > 0

