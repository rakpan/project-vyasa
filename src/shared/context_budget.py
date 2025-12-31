"""
Lightweight context budgeting and telemetry helpers.

Designed to be non-invasive: defaults are generous to avoid behavior changes,
but will warn (and optionally block) on clearly oversized requests relative to
model/context assumptions.
"""

from dataclasses import dataclass
from typing import Optional

from .model_registry import ModelConfig


# Default soft/hard limits per task type (tokens)
_DEFAULT_LIMITS = {
    "extract": (64000, 128000),
    "kg": (64000, 128000),
    "qa": (64000, 128000),
    "summarize": (48000, 96000),
    "adjudicate": (96000, 160000),
    "embeddings": (16000, 32000),
    "rerank": (32000, 64000),
}


@dataclass(frozen=True)
class ContextBudget:
    task_type: str
    soft_limit: int
    hard_limit: int

    def check(self, estimated_tokens: int) -> str:
        """Return 'ok', 'warn', or 'block' based on estimate."""
        if estimated_tokens > self.hard_limit:
            return "block"
        if estimated_tokens > self.soft_limit:
            return "warn"
        return "ok"


def estimate_tokens(text: str) -> int:
    """Rough token estimate from character length."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def get_context_budget(task_type: str, model: ModelConfig) -> ContextBudget:
    """Compute budget using model.max_context when available."""
    soft, hard = _DEFAULT_LIMITS.get(task_type, (64000, 128000))
    if model.max_context:
        # Constrain to model max
        hard = min(hard, model.max_context)
        soft = min(soft, model.max_context)
    return ContextBudget(task_type=task_type, soft_limit=soft, hard_limit=hard)
