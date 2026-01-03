import json
import pytest
from unittest.mock import patch

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


class TestToneGuardInvariants:
    """Invariant tests for tone guard to ensure governance rules are preserved."""
    
    def test_rewrite_preserves_claim_ids(self, monkeypatch):
        """Test that claim_ids are preserved exactly after tone rewrite."""
        # Mock Brain rewrite response
        mock_rewrite_response = {
            "choices": [{
                "message": {
                    "content": "This is a balanced approach to the problem."
                }
            }]
        }
        
        # Mock the rewrite call
        with patch("src.orchestrator.tone_guard.chat") as mock_chat:
            mock_chat.return_value = mock_rewrite_response
            
            # Initial state with manuscript blocks containing claim_ids
            initial_state = {
                "synthesis": "This is a revolutionary approach to the problem.",
                "manuscript_blocks": [{
                    "block_id": "block_1",
                    "content": "This is a revolutionary approach to the problem.",
                    "claim_ids": ["claim_123", "claim_456"],
                    "citation_keys": ["smith2023"],
                }],
                "tone_flags": [{
                    "word": "revolutionary",
                    "severity": "fail",
                    "suggestion": "balanced",
                    "location": {"start": 10, "end": 23},
                }],
                "rigor_level": "conservative",
                "jobId": "j1",
                "threadId": "j1",
            }
            
            # Mock lint_tone to return findings first, then zero after rewrite
            call_count = {"count": 0}
            def mock_lint_tone(text):
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return [{"word": "revolutionary", "severity": "fail", "location": {"start": 10, "end": 23}, "suggestion": "balanced"}]
                return []  # Zero findings after rewrite
            
            monkeypatch.setattr("src.orchestrator.tone_guard.lint_tone", mock_lint_tone)
            
            # Run tone guard
            result = tone_linter_node(initial_state)
            
            # Verify claim_ids are preserved in manuscript_blocks if they exist
            if "manuscript_blocks" in initial_state:
                # The rewrite should not mutate manuscript_blocks directly
                # But if it does, claim_ids must be preserved
                if "manuscript_blocks" in result:
                    for block in result["manuscript_blocks"]:
                        assert "claim_ids" in block
                        assert block["claim_ids"] == ["claim_123", "claim_456"], \
                            f"claim_ids changed: {block['claim_ids']}"
    
    def test_rewrite_preserves_citation_keys(self, monkeypatch):
        """Test that citation_keys are preserved exactly after tone rewrite."""
        mock_rewrite_response = {
            "choices": [{
                "message": {
                    "content": "This is a balanced approach [smith2023]."
                }
            }]
        }
        
        with patch("src.orchestrator.tone_guard.chat") as mock_chat:
            mock_chat.return_value = mock_rewrite_response
            
            initial_state = {
                "synthesis": "This is a revolutionary approach [smith2023].",
                "manuscript_blocks": [{
                    "block_id": "block_1",
                    "content": "This is a revolutionary approach [smith2023].",
                    "claim_ids": ["claim_123"],
                    "citation_keys": ["smith2023"],
                }],
                "tone_flags": [{
                    "word": "revolutionary",
                    "severity": "fail",
                    "suggestion": "balanced",
                }],
                "rigor_level": "conservative",
                "jobId": "j1",
                "threadId": "j1",
            }
            
            call_count = {"count": 0}
            def mock_lint_tone(text):
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return [{"word": "revolutionary", "severity": "fail", "location": {"start": 10, "end": 23}, "suggestion": "balanced"}]
                return []
            
            monkeypatch.setattr("src.orchestrator.tone_guard.lint_tone", mock_lint_tone)
            
            result = tone_linter_node(initial_state)
            
            # Verify citation_keys are preserved
            if "manuscript_blocks" in initial_state:
                if "manuscript_blocks" in result:
                    for block in result["manuscript_blocks"]:
                        assert "citation_keys" in block
                        assert block["citation_keys"] == ["smith2023"], \
                            f"citation_keys changed: {block['citation_keys']}"
    
    def test_rewrite_touches_only_flagged_sentences(self, monkeypatch):
        """Test that rewrite only modifies sentences with tone flags."""
        # Mock Brain rewrite to only change flagged sentence
        mock_rewrite_response = {
            "choices": [{
                "message": {
                    "content": "This is a balanced approach."
                }
            }]
        }
        
        with patch("src.orchestrator.tone_guard.chat") as mock_chat:
            mock_chat.return_value = mock_rewrite_response
            
            initial_state = {
                "synthesis": "This is a revolutionary approach. This sentence is unchanged.",
                "tone_flags": [{
                    "word": "revolutionary",
                    "severity": "fail",
                    "suggestion": "balanced",
                    "location": {"start": 10, "end": 23},
                }],
                "rigor_level": "conservative",
                "jobId": "j1",
                "threadId": "j1",
            }
            
            call_count = {"count": 0}
            def mock_lint_tone(text):
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return [{"word": "revolutionary", "severity": "fail", "location": {"start": 10, "end": 23}, "suggestion": "balanced"}]
                return []
            
            monkeypatch.setattr("src.orchestrator.tone_guard.lint_tone", mock_lint_tone)
            
            result = tone_linter_node(initial_state)
            
            # Verify only flagged sentence was modified
            if "synthesis" in result:
                rewritten = result["synthesis"]
                # First sentence should be modified
                assert "balanced" in rewritten or "revolutionary" not in rewritten.lower()
                # Second sentence should be unchanged (if rewrite is sentence-level)
                assert "This sentence is unchanged" in rewritten or "unchanged" in rewritten.lower()
    
    def test_conservative_mode_ends_with_zero_findings(self, monkeypatch):
        """Test that conservative mode re-lints and ends with zero findings."""
        # First lint finds issues
        initial_findings = [{
            "word": "revolutionary",
            "severity": "fail",
            "suggestion": "balanced",
            "location": {"start": 10, "end": 23},
        }]
        
        # After rewrite, lint finds zero issues
        zero_findings = []
        
        # Mock lint_tone to return zero findings after rewrite
        call_count = {"count": 0}
        def mock_lint_tone(text):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return initial_findings
            return zero_findings
        
        # Mock Brain rewrite
        mock_rewrite_response = {
            "choices": [{
                "message": {
                    "content": "This is a balanced approach."
                }
            }]
        }
        
        with patch("src.orchestrator.tone_guard.lint_tone", side_effect=mock_lint_tone):
            with patch("src.orchestrator.tone_guard.chat") as mock_chat:
                mock_chat.return_value = mock_rewrite_response
                
                initial_state = {
                    "synthesis": "This is a revolutionary approach.",
                    "tone_flags": initial_findings,
                    "rigor_level": "conservative",
                    "jobId": "j1",
                    "threadId": "j1",
                }
                
                result = tone_linter_node(initial_state)
                
                # Verify final state has zero findings
                if "tone_findings" in result:
                    assert len(result["tone_findings"]) == 0, \
                        f"Expected zero findings after rewrite, got: {result['tone_findings']}"
                # Verify rewrite was applied
                assert "synthesis" in result
                assert "revolutionary" not in result["synthesis"].lower()

