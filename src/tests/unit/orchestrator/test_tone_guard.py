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


def test_conservative_fails_and_triggers_rewrite(monkeypatch, mock_llm_client):
    """Test that conservative mode triggers rewrite when violations are detected."""
    # Track calls to chat
    calls = []
    
    # Meta response for all LLM calls
    meta = {
        "duration_ms": 100,
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        "expert_name": "Brain",
        "model_id": "test-model",
        "url_base": "http://fake-brain:8000",
        "path": "primary",
        "attempt": 1,
    }
    
    # Clean response (for rewrite) - returns rewritten sentence
    clean_response = (
        {"choices": [{"message": {"content": "balanced sentence."}}]},
        meta
    )
    
    # Create a wrapper that tracks calls and returns the rewrite response
    def tracking_side_effect(*args, **kwargs):
        calls.append(kwargs)
        return clean_response
    
    mock_llm_client.side_effect = tracking_side_effect
    
    # Mock get_brain_url to return a fake URL
    monkeypatch.setattr("src.shared.config.get_brain_url", lambda: "http://fake-brain:8000")
    
    # Smart lint_tone mock: only return findings if text contains "revolutionary"
    def smart_lint_tone(text):
        if "revolutionary" in text.lower():
            # Find the actual position of "revolutionary" in the text
            word_start = text.lower().find("revolutionary")
            if word_start >= 0:
                word_end = word_start + len("revolutionary")
                # Return finding with location matching the word position
                return [{"word": "revolutionary", "severity": "fail", "location": {"start": word_start, "end": word_end}, "suggestion": "balanced", "category": None}]
        return []  # No findings if text is clean
    
    monkeypatch.setattr("src.orchestrator.tone_guard.lint_tone", smart_lint_tone)
    
    state = {"synthesis": "revolutionary sentence.", "rigor_level": "conservative", "jobId": "j1", "threadId": "j1"}
    result = tone_linter_node(state)
    
    # Verify rewrite was triggered
    assert result.get("synthesis") != "revolutionary sentence.", f"Expected rewrite, but got: {result.get('synthesis')}"
    assert calls, "Expected rewrite to call chat"
    # Verify the rewritten text doesn't contain forbidden words
    assert "revolutionary" not in result.get("synthesis", "").lower()
    # Verify tone_findings are present
    assert "tone_findings" in result


def test_rewrite_preserves_bindings(monkeypatch, mock_llm_client):
    """Test that rewrite preserves claim_ids and citation_keys in state passed to chat."""
    # Track the state passed to chat to verify bindings are preserved
    captured_state = {}
    
    # Configure mock_llm_client to return cleaned text and capture state
    def capture_state_side_effect(*args, **kwargs):
        if "state" in kwargs:
            captured_state.update(kwargs["state"])
        return (
            {"choices": [{"message": {"content": "balanced sentence."}}]},
            {
                "duration_ms": 100,
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                "expert_name": "Brain",
                "model_id": "test-model",
                "url_base": "http://fake-brain:8000",
                "path": "primary",
                "attempt": 1,
            }
        )
    
    mock_llm_client.side_effect = capture_state_side_effect
    
    # Mock get_brain_url to return a fake URL
    monkeypatch.setattr("src.shared.config.get_brain_url", lambda: "http://fake-brain:8000")
    
    # Smart lint_tone mock: only return findings if text contains "revolutionary"
    def smart_lint_tone(text):
        if "revolutionary" in text.lower():
            # Find the actual position of "revolutionary" in the text
            word_start = text.lower().find("revolutionary")
            if word_start >= 0:
                word_end = word_start + len("revolutionary")
                # Return finding with location matching the word position
                return [{"word": "revolutionary", "severity": "fail", "location": {"start": word_start, "end": word_end}, "suggestion": "balanced", "category": None}]
        return []  # No findings if text is clean
    
    monkeypatch.setattr("src.orchestrator.tone_guard.lint_tone", smart_lint_tone)
    
    state = {
        "synthesis": "revolutionary sentence.",
        "rigor_level": "conservative",
        "jobId": "j1",
        "threadId": "j1",
        "claim_ids": ["c1", "c2"],
        "citation_keys": ["k1", "k2"],
    }
    result = tone_linter_node(state)
    
    # Verify bindings were passed to chat (preserved in state)
    assert captured_state.get("claim_ids") == ["c1", "c2"], f"Expected claim_ids in captured state, got: {captured_state}"
    assert captured_state.get("citation_keys") == ["k1", "k2"], f"Expected citation_keys in captured state, got: {captured_state}"
    # Verify the rewritten text doesn't contain forbidden words
    assert "revolutionary" not in result.get("synthesis", "").lower()
    assert "balanced" in result.get("synthesis", "")


def test_rewrite_removes_forbidden_words_in_conservative(monkeypatch, mock_llm_client):
    """Test that rewrite successfully removes forbidden words in conservative mode."""
    # First lint returns a fail, second lint returns no findings
    calls = {"lint": 0}

    def lint(text):
        calls["lint"] += 1
        if calls["lint"] == 1:
            return [{"word": "revolutionary", "severity": "fail", "location": {"start": 0, "end": len(text)}, "suggestion": "balanced", "category": None}]
        return []

    # Configure mock_llm_client to return cleaned text
    mock_llm_client.return_value = (
        {"choices": [{"message": {"content": "balanced sentence."}}]},
        {
            "duration_ms": 100,
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "expert_name": "Brain",
            "model_id": "test-model",
            "url_base": "http://fake-brain:8000",
            "path": "primary",
            "attempt": 1,
        }
    )
    
    # Patch at the source module where tone_linter_node actually calls lint_tone and chat
    monkeypatch.setattr("src.orchestrator.tone_guard.lint_tone", lint)
    # Mock get_brain_url to return a fake URL
    monkeypatch.setattr("src.shared.config.get_brain_url", lambda: "http://fake-brain:8000")

    state = {"synthesis": "revolutionary sentence.", "rigor_level": "conservative", "jobId": "j1", "threadId": "j1"}
    result = tone_linter_node(state)
    
    assert not result.get("tone_findings")
    assert "revolutionary" not in result.get("synthesis", "")
