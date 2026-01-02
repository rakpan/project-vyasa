import json
import types
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock

import pytest

from src.orchestrator.artifacts.manifest_builder import build_manifest
from src.orchestrator.nodes import artifact_registry_node
from src.shared.schema import ArtifactManifest


def _base_state() -> Dict[str, Any]:
    return {
        "job_id": "job-1",
        "jobId": "job-1",
        "threadId": "job-1",
        "project_id": "project-1",
    }


def test_density_is_computed_not_provided():
    state = _base_state() | {
        "manuscript_blocks": [
            {"block_id": "b1", "rq_id": "rq-1", "content": "word " * 50, "claim_ids": ["c1"], "citation_keys": []},
            {"block_id": "b2", "rq_id": "rq-2", "content": "word " * 50, "claim_ids": ["c2", "c3"], "citation_keys": []},
        ],
        "tables": [{"table_id": "t1", "rq_id": "rq-2", "source_claim_ids": ["c4"]}],
        "figures": [{"figure_id": "f1", "rq_id": "rq-1", "source_claim_ids": ["c5"]}],
        # Attempt to pass caller-provided metrics should be ignored by builder
        "metrics": {"claims_per_100_words": 999},
    }
    manifest = build_manifest(state, rigor_level="exploratory")
    assert isinstance(manifest, ArtifactManifest)
    assert manifest.metrics.total_words == 100
    # total_claims = block claims ONLY (3: c1, c2, c3) - table/figure source_claim_ids are NOT counted
    # This ensures claim density reflects manuscript evidence, not artifact metadata
    expected_density = 3 / (100 / 100)  # 3 claims from blocks only
    assert pytest.approx(manifest.metrics.claims_per_100_words) == expected_density
    # ensure provided metric did not override computed value
    assert manifest.metrics.claims_per_100_words != 999


def test_rq_id_general_only_allowed_in_exploratory():
    state = _base_state() | {
        "manuscript_blocks": [{"block_id": "b1", "rq_id": "general", "content": "sample text", "claim_ids": [], "citation_keys": []}],
    }
    # Conservative: must raise
    with pytest.raises(ValueError):
        build_manifest(state, rigor_level="conservative")

    # Exploratory: allowed, flagged but not fatal
    manifest = build_manifest(state, rigor_level="exploratory")
    assert any("rq_general" in flag for flag in manifest.flags)


def test_table_requires_source_claim_ids():
    state = _base_state() | {
        "manuscript_blocks": [{"block_id": "b1", "rq_id": "rq-1", "content": "text", "claim_ids": [], "citation_keys": []}],
        "tables": [{"table_id": "t1", "rq_id": "rq-1", "source_claim_ids": []}],
    }
    with pytest.raises(ValueError):
        build_manifest(state, rigor_level="conservative")

    manifest = build_manifest(state, rigor_level="exploratory")
    assert any("table:t1" in flag for flag in manifest.flags)


def test_figure_requires_source_claim_ids():
    state = _base_state() | {
        "manuscript_blocks": [{"block_id": "b1", "rq_id": "rq-1", "content": "text", "claim_ids": [], "citation_keys": []}],
        "vision_results": [{"artifact_id": "f1", "rq_id": "rq-1", "source_claim_ids": [], "caption": "c"}],
    }
    with pytest.raises(ValueError):
        build_manifest(state, rigor_level="conservative")

    manifest = build_manifest(state, rigor_level="exploratory")
    assert any("figure:f1" in flag for flag in manifest.flags)


def test_manifest_persist_called(monkeypatch, base_node_state):
    """Test that persist_manifest is called when artifact_registry_node runs.
    
    Note: This test patches persist_manifest (an internal function) which is acceptable
    since we're testing that artifact_registry_node calls it correctly. The function
    itself is business logic, not an I/O wrapper.
    """
    called = {"persist": 0}

    # Note: pathlib.Path.mkdir and builtins.open are automatically mocked by the firewall

    def fake_persist(manifest, db=None, telemetry_emitter=None, artifact_root=None):
        called["persist"] += 1
        # No actual file write - just track the call

    # Patch persist_manifest at the source module first (before nodes module uses it)
    monkeypatch.setattr("src.orchestrator.artifacts.manifest_builder.persist_manifest", fake_persist)
    
    # Also patch it in the nodes module where it's imported and used
    # artifact_registry_node imports persist_manifest from ..artifacts.manifest_builder
    # at module level, so we need to patch it in the nodes module namespace
    from src.orchestrator import nodes
    monkeypatch.setattr(nodes, "persist_manifest", fake_persist)
    
    # Note: ArangoClient is automatically mocked by the firewall, so artifact_registry_node
    # will create a mock DB when it calls ArangoClient()

    # Use base_node_state which includes all required fields including manifest
    state = {
        **base_node_state,
        "project_id": "p1",
        "job_id": "j1",
        "manuscript_blocks": [{"block_id": "b1", "rq_id": "rq-1", "content": "content here", "claim_ids": ["c1"], "citation_keys": ["k1"]}],
        "tables": [{"table_id": "t1", "rq_id": "rq-1", "source_claim_ids": ["c2"]}],
    }

    result = artifact_registry_node(state)
    assert called["persist"] == 1, f"persist_manifest should be called once, but was called {called['persist']} times"
    assert "artifacts" in result
