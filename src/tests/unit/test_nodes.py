"""
Unit tests for orchestrator workflow nodes (cartographer, critic, saver).

These tests mock external services to keep execution fast and deterministic.
"""

import json
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

from ...orchestrator import nodes
from ...orchestrator.nodes import cartographer_node, critic_node, saver_node, vision_node, select_images_for_vision
from ...orchestrator.state import PaperState


def make_chat_response(payload: Dict[str, Any]) -> Mock:
  """Create a mock OpenAI-style response object."""
  resp = Mock()
  resp.json.return_value = {
      "choices": [{"message": {"content": json.dumps(payload)}}]
  }
  resp.raise_for_status = Mock()
  resp.status_code = 200
  return resp


def test_cartographer_calls_cortex_and_returns_triples(monkeypatch):
  """Cartographer should call the Cortex URL and surface triples."""
  captured: Dict[str, Any] = {}

  def fake_post(url: str, json: Dict[str, Any], timeout: int = 0):
    captured["url"] = url
    captured["body"] = json
    return make_chat_response(
        {"triples": [{"subject": "A", "predicate": "relates", "object": "B", "confidence": 0.9}]}
    )

  # Patch the getter used by the node
  monkeypatch.setattr("src.orchestrator.nodes.get_worker_url", lambda: "http://fake-worker:1234")
  monkeypatch.setattr(nodes.requests, "post", fake_post)

  state: PaperState = {"raw_text": "Hello world", "critiques": []}
  result = cartographer_node(state)

  assert captured["url"].startswith("http://fake-worker:1234")
  triples = result["extracted_json"]["triples"]
  assert len(triples) == 1
  assert triples[0]["subject"] == "A"


def test_cartographer_node_with_project_context(monkeypatch):
  """Cartographer should run without crashing when project_context is provided."""
  captured: Dict[str, Any] = {}

  def fake_post(url: str, json: Dict[str, Any], timeout: int = 0):
    captured["body"] = json
    return make_chat_response(
        {"triples": [{"subject": "A", "predicate": "relates", "object": "B", "confidence": 0.9}]}
    )

  monkeypatch.setattr("src.orchestrator.nodes.get_worker_url", lambda: "http://fake-worker:1234")
  monkeypatch.setattr(nodes.requests, "post", fake_post)

  # State with project_context
  state: PaperState = {
    "raw_text": "Hello world",
    "critiques": [],
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


def test_cartographer_includes_critiques_in_prompt(monkeypatch):
  """Prior critiques must be included in the request prompt."""
  captured: Dict[str, Any] = {}

  def fake_post(url: str, json: Dict[str, Any], timeout: int = 0):
    captured["body"] = json
    return make_chat_response({"triples": []})

  monkeypatch.setattr(nodes.requests, "post", fake_post)

  state: PaperState = {"raw_text": "Test", "critiques": ["missing sources"], "revision_count": 1}
  cartographer_node(state)

  messages: List[Dict[str, str]] = captured["body"]["messages"]
  assert any("missing sources" in m.get("content", "").lower() for m in messages)


def test_cartographer_raises_on_empty_text():
  """Empty text should raise an error early."""
  with pytest.raises(ValueError):
    cartographer_node({"raw_text": ""})


def test_critic_sets_pass_status(monkeypatch):
  """Critic should pass through status and avoid incrementing revisions on pass."""
  def fake_post(url: str, json: Dict[str, Any], timeout: int = 0):
    return make_chat_response({"status": "pass", "critiques": []})

  monkeypatch.setattr(nodes.requests, "post", fake_post)
  state: PaperState = {"raw_text": "Test", "extracted_json": {"triples": [{}]}, "revision_count": 0}
  result = critic_node(state)

  assert result["critic_status"] == "pass"
  assert result["revision_count"] == 0


def test_critic_increments_revision_on_fail(monkeypatch):
  """Failures must increment revision_count and carry critiques."""
  def fake_post(url: str, json: Dict[str, Any] = None, timeout: int = 0):
    # For the legacy path brain endpoint
    return make_chat_response({"status": "fail", "critiques": ["missing triple"]})

  monkeypatch.setattr(nodes.requests, "post", fake_post)
  monkeypatch.setattr("src.orchestrator.nodes.get_brain_url", lambda: "http://fake-brain:1234")
  # Mock role_registry.get_role to avoid DB dependency
  mock_role = Mock()
  mock_role.system_prompt = "You are a critic."
  mock_role.allowed_tools = []
  monkeypatch.setattr("src.orchestrator.nodes.role_registry.get_role", lambda name: mock_role)

  state: PaperState = {"raw_text": "Test", "extracted_json": {"triples": []}, "revision_count": 1}
  result = critic_node(state)

  assert result["critic_status"] == "fail"
  assert result["revision_count"] == 2
  assert "missing triple" in result["critiques"][0]


def test_saver_persists_to_arango(monkeypatch):
  """Saver should attempt to write extraction results to Arango without raising."""
  inserted: List[Dict[str, Any]] = []

  class FakeCollection:
    def __init__(self):
      self.docs = inserted

    def insert(self, doc):
      self.docs.append(doc)
      return {"_key": f"key{len(self.docs)}", "_id": f"extractions/key{len(self.docs)}", "_rev": "1"}

    def has_index(self, *_args, **_kwargs):
      return True

    def add_index(self, *_args, **_kwargs):
      return None

  class FakeDB:
    def __init__(self):
      self.collection_obj = FakeCollection()

    def has_collection(self, name):
      return True

    def create_collection(self, name, edge=False):
      return self.collection_obj

    def collection(self, name):
      return self.collection_obj

  class FakeClient:
    def __init__(self, hosts):
      self.db_obj = FakeDB()

    def db(self, *args, **kwargs):
      return self.db_obj

  monkeypatch.setattr(nodes, "ArangoClient", FakeClient)

  state: PaperState = {"extracted_json": {"triples": [{"subject": "A", "predicate": "p", "object": "B"}]}, "critiques": []}
  new_state = saver_node(state)

  assert len(inserted) == 1
  assert inserted[0]["status"] in ("pass", "needs_manual_review")
  assert "save_receipt" in new_state
  assert new_state["save_receipt"]["status"] == "SAVED"


def test_saver_failure_propagates(monkeypatch):
  """Saver node should re-raise exceptions (not swallow them)."""
  class FakeCollection:
    def insert(self, doc):
      raise RuntimeError("db down")

  class FakeDB:
    def has_collection(self, *_args, **_kwargs):
      return True
    def create_collection(self, *_args, **_kwargs):
      return FakeCollection()
    def collection(self, *_args, **_kwargs):
      return FakeCollection()

  class FakeClient:
    def __init__(self, hosts):
      self.db_obj = FakeDB()
    def db(self, *_args, **_kwargs):
      return self.db_obj

  monkeypatch.setattr(nodes, "ArangoClient", FakeClient)

  state: PaperState = {"extracted_json": {"triples": []}, "critiques": []}
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


def test_vision_injects_context(monkeypatch, tmp_path):
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

  monkeypatch.setattr("src.orchestrator.nodes.requests.post", fake_post)
  monkeypatch.setattr("src.orchestrator.nodes.get_vision_url", lambda: "http://vision")

  state: PaperState = {"raw_text": "Base text", "image_paths": [img.as_posix()]}
  updated = vision_node(state)
  assert "Vision Extracts" in updated["raw_text"]
  assert "fig1.png" in updated["raw_text"]
  assert "vision_results" in updated
  assert len(updated["vision_results"]) == 1
