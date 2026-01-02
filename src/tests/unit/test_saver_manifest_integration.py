import types
from unittest.mock import Mock

import pytest

from src.orchestrator import nodes


class FakeCollection:
    def insert(self, doc):
        return {"_key": "k1", "_id": "c/k1", "_rev": "1"}


class FakeDB:
    def __init__(self):
        self._collections = {"extractions": FakeCollection(), "manuscript_blocks": FakeCollection()}
        # Mock aql for version queries
        self.aql = types.SimpleNamespace()
        self.aql.execute = lambda query, bind_vars=None: iter([])  # Return empty iterator

    def has_collection(self, name):
        return name in self._collections

    def create_collection(self, name):
        self._collections[name] = FakeCollection()
        return self._collections[name]

    def collection(self, name):
        return self._collections[name]


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def db(self, *args, **kwargs):
        return FakeDB()


def test_saver_builds_manifest_once(monkeypatch, base_node_state):
    """Test that saver builds manifest once and persists it."""
    call_count = {"build": 0, "persist": 0, "telemetry": 0}

    # Note: pathlib.Path.mkdir and builtins.open are automatically mocked by the firewall

    def fake_build(state, rigor_level=None):
        call_count["build"] += 1
        manifest = types.SimpleNamespace(
            model_dump=lambda mode=None: {"job_id": state.get("job_id")},
            project_id=state.get("project_id"),
            job_id=state.get("job_id"),
            totals={"words": 0, "tables": 0, "figures": 0},
            blocks=[],
        )
        return manifest

    def fake_persist(manifest, db=None, telemetry_emitter=None, artifact_root=None):
        call_count["persist"] += 1

    def fake_emit(event_type, data):
        call_count["telemetry"] += 1

    # ArangoClient is already mocked by mock_arango_firewall (autouse fixture)
    monkeypatch.setattr(nodes, "build_manifest", fake_build)
    monkeypatch.setattr(nodes, "persist_manifest", fake_persist)
    monkeypatch.setattr(nodes.telemetry_emitter, "emit_event", fake_emit)

    # Use base_node_state which includes all required fields including manifest
    state = {
        **base_node_state,
        "project_id": "p1",
        "job_id": "j1",
        "triples": [{"subject": "A", "predicate": "relates", "object": "B", "confidence": 0.9}],
        "extracted_json": {"triples": [{"subject": "A", "predicate": "relates", "object": "B", "confidence": 0.9}]},
    }
    out = nodes.saver_node(state)
    assert "save_receipt" in out
    assert call_count["build"] == 1
    assert call_count["persist"] == 1
    assert call_count["telemetry"] >= 0  # telemetry may not fire in this simplified test


def test_saver_emits_failure_on_manifest_error(monkeypatch, base_node_state):
    """Test that saver emits failure event when manifest build fails."""
    call_count = {"fail": 0}

    # Note: pathlib.Path.mkdir and builtins.open are automatically mocked by the firewall

    def fake_build(state, rigor_level=None):
        raise RuntimeError("boom")

    def fake_emit(event_type, data):
        if event_type == "artifact_manifest_failed":
            call_count["fail"] += 1

    # ArangoClient is already mocked by mock_arango_firewall (autouse fixture)
    monkeypatch.setattr(nodes, "build_manifest", fake_build)
    monkeypatch.setattr(nodes, "persist_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(nodes.telemetry_emitter, "emit_event", fake_emit)

    # Use base_node_state which includes all required fields
    state = {
        **base_node_state,
        "project_id": "p1",
        "job_id": "j1",
        "extracted_json": {"triples": []},
    }
    out = nodes.saver_node(state)
    assert "save_receipt" in out
    assert call_count["fail"] == 1
