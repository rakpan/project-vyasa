"""
Runtime detection and KV/cache policies.

Keeps changes isolated: exposes helpers to apply context bands and
concurrency hints without altering caller behavior.
"""

import os
from dataclasses import dataclass
from typing import Optional

from .model_registry import ModelConfig


@dataclass(frozen=True)
class ContextBand:
    min_tokens: int
    max_tokens: int


CONTEXT_BANDS = {
    "extract": ContextBand(8_000, 32_000),
    "kg": ContextBand(16_000, 64_000),
    "adjudicate": ContextBand(32_000, 128_000),
    "narrative": ContextBand(16_000, 64_000),
}


def detect_runtime(provider: str) -> str:
    """Map provider to runtime string."""
    prov = provider.lower()
    if "sglang" in prov:
        return "sglang"
    if "ollama" in prov:
        return "ollama"
    if "tensor" in prov or "trt" in prov:
        return "tensorrt-llm"
    if "vllm" in prov:
        return "vllm"
    return prov


def kv_policy_for(model: ModelConfig) -> Optional[str]:
    """Return kv policy hint (non-authoritative).
    
    Uses registry kv_policy field as a hint only. Actual KV policy is configured
    in deploy/docker-compose.yml command flags (e.g., --mem-fraction-static).
    This function is for informational/reference purposes only.
    """
    if model.kv_policy:
        return model.kv_policy  # Non-authoritative hint from registry
    runtime = detect_runtime(model.provider)
    if runtime == "sglang":
        # SGLang supports mem-fraction-static; actual value set in docker-compose.yml
        return "mem-fraction-static (compose)"
    if runtime == "ollama":
        return None
    return None


def concurrency_limit_for(context_len: int) -> Optional[int]:
    """
    Suggest a concurrency limit given context length. Conservative to avoid KV blowups.
    """
    if context_len >= 128_000:
        return 1
    if context_len >= 64_000:
        return 2
    if context_len >= 32_000:
        return 4
    return None  # no suggestion
