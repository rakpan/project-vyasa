"""
Opt-in model router for Project Vyasa.

Keeps current behavior by default; routing can be enabled via feature flags.
"""

from dataclasses import dataclass
from typing import Optional

from .model_registry import get_model_config, ModelConfig


@dataclass(frozen=True)
class RouteRequest:
    task_type: str  # e.g., extract, qa, adjudicate
    context_needed: Optional[int] = None  # estimated tokens
    deterministic: bool = False  # structured output preference


class ModelRouter:
    """Minimal router with example rules; safe by default."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def route(self, request: RouteRequest) -> ModelConfig:
        """Return a ModelConfig based on request. Falls back to defaults when disabled."""
        if not self.enabled:
            return self._default_model(request.task_type)

        task = request.task_type.lower()

        # Example routes
        if task in ("extract", "kg"):
            # Structured extraction prefers worker (fp4, deterministic params externally)
            return get_model_config("worker")

        if task in ("qa", "summarize"):
            # General QA goes to brain (larger model) when available
            return get_model_config("brain")

        if task in ("adjudicate", "conflict"):
            # Reasoning/adjudication uses brain
            return get_model_config("brain")

        if task in ("vision",):
            return get_model_config("vision")

        if task in ("embeddings", "rerank"):
            return get_model_config("embedder")

        # Fallback: worker
        return get_model_config("worker")

    def _default_model(self, task_type: str) -> ModelConfig:
        """Mirror existing behavior: worker for extraction, brain for critic, vision for vision."""
        task = task_type.lower()
        if task in ("extract", "kg"):
            return get_model_config("worker")
        if task in ("adjudicate", "conflict"):
            return get_model_config("brain")
        if task in ("vision",):
            return get_model_config("vision")
        if task in ("embeddings", "rerank"):
            return get_model_config("embedder")
        # Default fallback: brain for general QA/summarize, worker otherwise
        if task in ("qa", "summarize"):
            return get_model_config("brain")
        return get_model_config("worker")


# Feature flag (can be toggled in calling code)
DEFAULT_ROUTER = ModelRouter(enabled=False)
