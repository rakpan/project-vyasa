from typing import Any, Dict

import pytest

from src.shared import llm_client
from src.shared.opik_client import compute_prompt_hash


class DummyResp:
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_opik_disabled_no_effect(monkeypatch):
    monkeypatch.setattr(llm_client, "track_llm_call", lambda meta, fn: fn())
    monkeypatch.setattr(llm_client, "compute_prompt_hash", lambda m, t: "hash")

    def fake_post(url, json=None, timeout=None):
        return DummyResp({"choices": [{"message": {"content": "ok"}}], "usage": {}})

    monkeypatch.setattr(llm_client.requests, "post", fake_post)

    data, meta = llm_client.chat(
        primary_url="http://x",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        state={"job_id": "j1", "project_id": "p1"},
    )
    assert data["choices"][0]["message"]["content"] == "ok"


def test_opik_failure_does_not_break(monkeypatch):
    # Force track_llm_call path but raise inside _safe_post
    calls = {"track": 0}

    def fake_track(meta, fn):
        calls["track"] += 1
        return fn()

    def fake_post(url, json=None, timeout=None):
        return DummyResp({"choices": [{"message": {"content": "ok"}}], "usage": {}})

    monkeypatch.setattr(llm_client, "track_llm_call", fake_track)
    monkeypatch.setattr(llm_client.requests, "post", fake_post)

    data, meta = llm_client.chat(
        primary_url="http://x",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        state={"job_id": "j1", "project_id": "p1"},
    )
    assert data["choices"][0]["message"]["content"] == "ok"
    assert calls["track"] >= 1


def test_prompt_hash_stable():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    h1 = compute_prompt_hash(msgs, [{"name": "t"}])
    h2 = compute_prompt_hash(msgs, [{"name": "t"}])
    assert h1 == h2
    h3 = compute_prompt_hash(msgs + [{"role": "assistant", "content": "a"}], [{"name": "t"}])
    assert h1 != h3


def test_metadata_tags_injected(monkeypatch):
    captured = {}

    def fake_track(meta, fn):
        captured.update(meta)
        return fn()

    def fake_post(url, json=None, timeout=None):
        return DummyResp({"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1}})

    monkeypatch.setattr(llm_client, "track_llm_call", fake_track)
    monkeypatch.setattr(llm_client.requests, "post", fake_post)

    data, meta = llm_client.chat(
        primary_url="http://x",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        state={"job_id": "j1", "project_id": "p1"},
        node_name="critic",
        expert_name="Brain",
    )
    assert captured.get("job_id") == "j1"
    assert captured.get("node_name") == "critic"
    assert captured.get("expert_type") == "Brain"
