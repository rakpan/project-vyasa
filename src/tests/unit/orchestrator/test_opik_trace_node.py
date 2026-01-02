from src.orchestrator.telemetry import trace_node
from src.shared import opik_client


def test_trace_node_opik_failure_safe(monkeypatch):
    # Force Opik enabled
    monkeypatch.setattr(opik_client, "get_opik_client", lambda: {"base_url": "http://fake", "headers": {}, "timeout": 1, "project": "p"})
    monkeypatch.setattr(opik_client, "track_llm_call", lambda meta, fn: (_ for _ in ()).throw(RuntimeError("boom")))

    @trace_node
    def sample(state):
        return {**state, "revision_count": 1}

    # Should not raise even though track_llm_call throws
    out = sample({"job_id": "j1", "project_id": "p1", "extracted_json": {"triples": []}})
    assert out["revision_count"] == 1


def test_trace_node_summary_does_not_include_raw(monkeypatch):
    captured = {}

    def fake_track(meta, fn):
        captured.update(meta)
        return fn()

    monkeypatch.setattr(opik_client, "get_opik_client", lambda: {"base_url": "http://fake", "headers": {}, "timeout": 1, "project": "p"})
    monkeypatch.setattr(opik_client, "track_llm_call", fake_track)

    @trace_node
    def sample(state):
        return {
            "job_id": "j1",
            "project_id": "p1",
            "raw_text": "secret",
            "manuscript_blocks": [{"content": "should not leak"}],
            "extracted_json": {"triples": [1, 2]},
        }

    sample({})
    assert "raw_text" not in str(captured)
    assert captured.get("summary", {}).get("triples_count") == 2
