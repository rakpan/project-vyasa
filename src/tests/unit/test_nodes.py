"""
Unit tests for orchestrator workflow nodes (cartographer, critic, saver).

These tests use centralized fixtures from conftest.py for consistent mocking.
"""

import json
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

from ...orchestrator import nodes
from ...orchestrator.nodes import (
  cartographer_node,
  critic_node,
  saver_node,
  vision_node,
  select_images_for_vision,
  reframing_node,
)
from ...orchestrator.state import ResearchState
from ...shared.schema import RecommendedNextStep, ConflictType, ConflictProducer, ConflictSeverity


def test_cartographer_calls_cortex_and_returns_triples(monkeypatch, base_node_state, mock_llm_client):
  """Cartographer should call the Cortex URL and surface triples."""
  captured: Dict[str, Any] = {}

  # Configure mock_llm_client to capture calls and return test data
  def capture_and_return(*args, **kwargs):
    url = kwargs.get("primary_url") or kwargs.get("url_base") or ""
    captured["url"] = url
    captured["body"] = kwargs.get("messages", [])
    return (
        {
            "choices": [{
                "message": {
                    "content": json.dumps({"triples": [{"subject": "A", "predicate": "relates", "object": "B", "confidence": 0.9}]})
                }
            }]
        },
        {"duration_ms": 100, "usage": {}, "expert_name": "Worker", "model_id": "test", "url_base": url, "path": "primary", "attempt": 1}
    )
  
  mock_llm_client.side_effect = capture_and_return

  # Patch the getter used by the node
  monkeypatch.setattr("src.orchestrator.nodes.get_worker_url", lambda: "http://fake-worker:1234")
  # Also patch route_to_expert to ensure it returns the expected URL
  monkeypatch.setattr("src.orchestrator.nodes.route_to_expert", lambda *args, **kwargs: ("http://fake-worker:1234", "Worker", "test-model"))

  # Use base_node_state fixture which includes all required fields including 'url'
  state: ResearchState = {**base_node_state, "raw_text": "Hello world"}
  result = cartographer_node(state)

  assert captured["url"].startswith("http://fake-worker:1234")
  triples = result["extracted_json"]["triples"]
  assert len(triples) == 1
  assert triples[0]["subject"] == "A"


def test_cartographer_node_with_project_context(monkeypatch, base_node_state, mock_llm_client):
  """Cartographer should run without crashing when project_context is provided."""
  # Configure mock_llm_client to return test data
  mock_llm_client.return_value = (
      {
          "choices": [{
              "message": {
                  "content": json.dumps({"triples": [{"subject": "A", "predicate": "relates", "object": "B", "confidence": 0.9}]})
              }
          }]
      },
      {"duration_ms": 100, "usage": {}, "expert_name": "Worker", "model_id": "test", "url_base": "http://fake-worker:1234", "path": "primary", "attempt": 1}
  )

  monkeypatch.setattr("src.orchestrator.nodes.get_worker_url", lambda: "http://fake-worker:1234")
  monkeypatch.setattr("src.orchestrator.nodes.route_to_expert", lambda *args, **kwargs: ("http://fake-worker:1234", "Worker", "test-model"))

  # State with project_context - use base_node_state as foundation
  state: ResearchState = {
    **base_node_state,
    "raw_text": "Hello world",
    "project_id": "550e8400-e29b-41d4-a716-446655440000",
    "project_context": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Test Project",
      "thesis": "Test thesis",
      "research_questions": ["RQ1"],
      "seed_files": [],
      "created_at": "2024-01-15T10:30:00Z",
    },
  }
  
  # Should not raise
  result = cartographer_node(state)
  
  # Verify triples are present
  assert "extracted_json" in result
  assert "triples" in result["extracted_json"]
  assert len(result["extracted_json"]["triples"]) == 1


def test_cartographer_includes_critiques_in_prompt(monkeypatch, base_node_state, mock_llm_client):
  """Prior critiques must be included in the request prompt."""
  captured: Dict[str, Any] = {}

  # Configure mock_llm_client to capture messages
  def capture_messages(*args, **kwargs):
    captured["body"] = kwargs.get("messages", [])
    return (
        {
            "choices": [{
                "message": {
                    "content": json.dumps({"triples": []})
                }
            }]
        },
        {"duration_ms": 100, "usage": {}, "expert_name": "Worker", "model_id": "test", "url_base": "http://fake-worker:1234", "path": "primary", "attempt": 1}
    )
  
  mock_llm_client.side_effect = capture_messages
  monkeypatch.setattr("src.orchestrator.nodes.get_worker_url", lambda: "http://fake-worker:1234")
  monkeypatch.setattr("src.orchestrator.nodes.route_to_expert", lambda *args, **kwargs: ("http://fake-worker:1234", "Worker", "test-model"))

  state: ResearchState = {**base_node_state, "raw_text": "Test", "critiques": ["missing sources"], "revision_count": 1}
  cartographer_node(state)

  messages: List[Dict[str, str]] = captured["body"]
  assert any("missing sources" in m.get("content", "").lower() for m in messages)


def test_cartographer_raises_on_empty_text(base_node_state):
  """Empty text should raise an error early."""
  # Use base_node_state but override raw_text to empty
  state = {**base_node_state, "raw_text": ""}
  with pytest.raises(ValueError):
    cartographer_node(state)


def test_critic_sets_pass_status(monkeypatch, base_node_state, mock_llm_client):
  """Critic should pass through status and avoid incrementing revisions on pass."""
  # Configure mock_llm_client to return pass status
  mock_llm_client.return_value = (
      {
          "choices": [{
              "message": {
                  "content": json.dumps({"status": "pass", "critiques": []})
              }
          }]
      },
      {"duration_ms": 100, "usage": {}, "expert_name": "Critic", "model_id": "test", "url_base": "http://fake-brain:30000", "path": "primary", "attempt": 1}
  )

  state: ResearchState = {**base_node_state, "raw_text": "Test", "extracted_json": {"triples": [{}]}, "revision_count": 0}
  result = critic_node(state)

  assert result["critic_status"] == "pass"
  assert result["revision_count"] == 0


def test_critic_increments_revision_on_fail(monkeypatch, base_node_state, mock_llm_client):
  """Failures must increment revision_count and carry critiques."""
  # Configure mock_llm_client to return fail status
  mock_llm_client.return_value = (
      {
          "choices": [{
              "message": {
                  "content": json.dumps({"status": "fail", "critiques": ["missing triple"]})
              }
          }]
      },
      {"duration_ms": 100, "usage": {}, "expert_name": "Critic", "model_id": "test", "url_base": "http://fake-brain:30000", "path": "primary", "attempt": 1}
  )

  state: ResearchState = {**base_node_state, "raw_text": "Test", "extracted_json": {"triples": [{}]}, "revision_count": 1}
  result = critic_node(state)

  assert result["critic_status"] == "fail"
  assert result["revision_count"] == 2
  assert "missing triple" in result["critiques"][0]


def test_saver_persists_to_arango(mock_arango_firewall, base_node_state):
  """Saver should attempt to write extraction results to Arango without raising."""
  # Track insertions via a list
  inserted: List[Dict[str, Any]] = []
  
  # Create a custom mock collection that tracks inserts
  class TrackingCollection:
    def __init__(self):
      self.docs = inserted
    
    def insert(self, doc):
      self.docs.append(doc)
      return {"_key": f"key{len(self.docs)}", "_id": f"extractions/key{len(self.docs)}", "_rev": "1"}
    
    def has_index(self, *_args, **_kwargs):
      return True
    
    def add_index(self, *_args, **_kwargs):
      return None
  
  # Configure the firewall's mock to use our tracking collection
  # The firewall fixture yields a function that returns mock clients
  # All clients share the same mock_db, so we configure it through any client
  tracking_collection = TrackingCollection()
  
  # Get the mock client from the firewall (this is the same function that ArangoClient is patched to)
  mock_client = mock_arango_firewall("http://fake:8529")
  mock_db = mock_client.db()
  
  # Configure the mock DB explicitly - this affects all ArangoClient instances
  mock_db.collection.return_value = tracking_collection
  mock_db.create_collection.return_value = tracking_collection
  mock_db.has_collection.return_value = True

  state: ResearchState = {**base_node_state, "extracted_json": {"triples": [{"subject": "A", "predicate": "p", "object": "B"}]}}
  new_state = saver_node(state)

  assert len(inserted) == 1
  assert inserted[0]["status"] in ("pass", "needs_manual_review")
  assert "save_receipt" in new_state
  assert new_state["save_receipt"]["status"] == "SAVED"


def test_saver_failure_propagates(mock_arango_firewall, base_node_state):
  """Saver node should re-raise exceptions (not swallow them)."""
  # Create a mock collection that raises on insert
  class FailingCollection:
    def insert(self, doc):
      raise RuntimeError("db down")
    
    def has_index(self, *_args, **_kwargs):
      return True
    
    def add_index(self, *_args, **_kwargs):
      return None
  
  # Configure the firewall's mock to use our failing collection
  # The firewall fixture yields a function that returns mock clients
  # All clients share the same mock_db, so we configure it through any client
  failing_collection = FailingCollection()
  
  # Get the mock client from the firewall (this is the same function that ArangoClient is patched to)
  mock_client = mock_arango_firewall("http://fake:8529")
  mock_db = mock_client.db()
  
  # Configure the mock DB explicitly - this affects all ArangoClient instances
  mock_db.collection.return_value = failing_collection
  mock_db.create_collection.return_value = failing_collection
  mock_db.has_collection.return_value = True

  state: ResearchState = {**base_node_state, "extracted_json": {"triples": []}}
  with pytest.raises(RuntimeError, match="db down"):
    saver_node(state)


def test_select_images_for_vision_limits_and_prioritizes(tmp_path):
  imgs = []
  # preferred names
  for name in ["fig1.png", "table_big.png", "note.png", "chart.png", "extra.png", "overflow.png"]:
    p = tmp_path / name
    p.write_bytes(b"0" * (600_000 if "big" in name else 10))
    imgs.append(str(p))

  selected = select_images_for_vision(imgs)
  assert len(selected) <= 5  # default limit
  # Preferred ones should be first
  assert any("fig1" in s for s in selected[:2])


def test_vision_injects_context(monkeypatch, tmp_path, base_node_state):
  # Create fake images
  img = tmp_path / "fig1.png"
  img.write_bytes(b"fake")

  def fake_post(url, data=None, files=None, timeout=0):
    assert files is not None
    resp = Mock()
    resp.json.return_value = {
        "image_path": img.as_posix(),
        "caption": "A test figure",
        "extracted_facts": [{"key": "val", "value": "42", "unit": "", "confidence": 0.8}],
        "tables": [],
        "confidence": 0.9,
    }
    resp.raise_for_status = Mock()
    return resp

  # Note: requests.post is automatically mocked by the firewall in conftest.py
  monkeypatch.setattr("src.orchestrator.nodes.get_vision_url", lambda: "http://vision")

  state: ResearchState = {**base_node_state, "raw_text": "Base text", "image_paths": [img.as_posix()]}
  updated = vision_node(state)
  assert "Vision Extracts" in updated["raw_text"]
  assert "fig1.png" in updated["raw_text"]
  assert "vision_results" in updated
  assert len(updated["vision_results"]) == 1


def test_reframing_sets_needs_signoff_on_interrupt_failure(monkeypatch, base_node_state):
  """Reframing node should mark needs_signoff even if interrupt raises."""
  conflict_report = {
    "report_id": "r1",
    "project_id": "p1",
    "job_id": "job-1",
    "doc_hash": "abc",
    "revision_count": 2,
    "critic_status": "fail",
    "deadlock": True,
    "deadlock_type": "conflict",
    "conflict_items": [
      {
        "conflict_id": "c1",
        "summary": "deadlock",
        "details": "Test conflict details",
        "produced_by": ConflictProducer.CRITIC,
        "conflict_type": ConflictType.EVIDENCE_BINDING_FAILURE,
        "severity": ConflictSeverity.BLOCKER,
        "confidence": 0.9
      }
    ],
    "conflict_hash": "h1",
    "recommended_next_step": RecommendedNextStep.TRIGGER_REFRAMING,
    "created_at": datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
  }

  # Mock interrupt to raise an exception
  def failing_interrupt(payload=None):
    raise RuntimeError("boom")
  
  monkeypatch.setattr(nodes, "interrupt", failing_interrupt)
  # Also need to mock store_reframing_proposal, update_job_status, and telemetry_emitter to avoid real calls
  monkeypatch.setattr("src.orchestrator.nodes.store_reframing_proposal", lambda x: "proposal-123")
  # Mock update_job_status - it's called with job_id, status, and optional kwargs
  def mock_update_job_status(job_id, status, **kwargs):
    pass
  monkeypatch.setattr("src.orchestrator.nodes.update_job_status", mock_update_job_status)
  # Mock telemetry_emitter to avoid AttributeError
  mock_emitter = Mock()
  mock_emitter.emit_event = Mock()
  monkeypatch.setattr("src.orchestrator.nodes.telemetry_emitter", mock_emitter)
  
  # Use base_node_state which includes all required fields (jobId, threadId, project_id, etc.)
  state: ResearchState = {
    **base_node_state, 
    "revision_count": 2, 
    "conflict_report": conflict_report, 
    "job_id": "job-1",
  }
  result = reframing_node(state)
  # The reframing_node should return needs_signoff=True even when interrupt raises
  # Check that needs_signoff is explicitly True (not just present)
  assert result.get("needs_signoff") is True, (
    f"Expected needs_signoff=True, got {result.get('needs_signoff')}, "
    f"result keys: {list(result.keys())}, state keys: {list(state.keys())}, "
    f"conflict_report keys: {list(conflict_report.keys())}"
  )
import asyncio
import json

import pytest


class MockCompiledGraph:
    def __init__(self, events):
        self._events = events

    async def astream_events(self, state, config=None, version=None):
        for ev in self._events:
            yield ev
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_astream_events_v2_node_start():
    events = [
        {"event": "on_node_start", "name": "brain", "state": {}},
        {"event": "on_node_start", "name": "logician", "state": {}},
        {"event": "on_node_start", "name": "vision", "state": {}},
        {"event": "on_end", "state": {"done": True}},
    ]
    graph = MockCompiledGraph(events)
    seen = []
    async for ev in graph.astream_events({}, version="v2"):
        if ev.get("event") == "on_node_start":
            seen.append(ev["name"])
    assert seen == ["brain", "logician", "vision"]
