"""
Lightweight eval harness for CI friendliness.

Notes:
- Uses placeholder logic; does not call live models.
- Provides structure for schema checks, citation validation, determinism, and latency benchmarking.
- Hook in real model calls or fixtures when available.
"""

import json
import time
from typing import Dict, Any

import pytest


def is_schema_valid(payload: Dict[str, Any]) -> bool:
    triples = payload.get("triples")
    if triples is None or not isinstance(triples, list):
        return False
    for t in triples:
        if not isinstance(t, dict):
            return False
        if not all(k in t for k in ("subject", "predicate", "object")):
            return False
    return True


def citations_are_valid(payload: Dict[str, Any]) -> bool:
    # Placeholder: ensures evidence has source_pointer with snippet/doc_hash
    triples = payload.get("triples") or []
    for t in triples:
        sp = t.get("source_pointer") or {}
        if not sp:
            return False
        if "doc_hash" not in sp or "snippet" not in sp:
            return False
    return True


def fake_model_call(input_text: str, delay: float = 0.01) -> Dict[str, Any]:
    time.sleep(delay)
    return {
        "triples": [
            {
                "subject": "A",
                "predicate": "relates_to",
                "object": "B",
                "source_pointer": {"doc_hash": "abc", "snippet": input_text[:10]},
            }
        ]
    }


@pytest.mark.parametrize("input_text", ["short text", "another text"])
def test_schema_and_citations(input_text: str):
    output = fake_model_call(input_text)
    assert is_schema_valid(output)
    assert citations_are_valid(output)


def test_determinism_within_tolerance():
    out1 = fake_model_call("deterministic")
    out2 = fake_model_call("deterministic")
    assert out1 == out2


@pytest.mark.parametrize(
    "context_len, max_latency_ms",
    [
        (8_000, 500),
        (32_000, 1_500),
        (64_000, 3_000),
    ],
)
def test_latency_budget(context_len: int, max_latency_ms: int):
    start = time.time()
    fake_model_call("x" * context_len, delay=0.01)  # placeholder delay
    elapsed_ms = (time.time() - start) * 1000
    assert elapsed_ms <= max_latency_ms
