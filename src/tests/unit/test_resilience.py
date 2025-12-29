"""
Resilience tests for orchestrator nodes.
"""

import json
import requests
import pytest
from unittest.mock import Mock

from ...orchestrator import nodes
from ...orchestrator.nodes import cartographer_node
from ...orchestrator.state import PaperState


def test_cartographer_handles_timeout(monkeypatch):
    """SGLang timeout should result in empty triples (no crash)."""
    def fake_post(*args, **kwargs):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(nodes.requests, "post", fake_post)

    state: PaperState = {"raw_text": "Test text"}
    result = cartographer_node(state)

    assert "extracted_json" in result
    assert "triples" in result["extracted_json"]
    assert result["extracted_json"]["triples"] == []


def test_cartographer_handles_garbage_json(monkeypatch):
    """Garbage JSON response should be handled gracefully."""
    def fake_post(*args, **kwargs):
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.json.return_value = {
            "choices": [{"message": {"content": "I am not JSON"}}]
        }
        return resp

    monkeypatch.setattr(nodes.requests, "post", fake_post)

    state: PaperState = {"raw_text": "Test text"}
    result = cartographer_node(state)

    assert "extracted_json" in result
    assert result["extracted_json"]["triples"] == []
