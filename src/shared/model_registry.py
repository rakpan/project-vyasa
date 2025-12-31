"""
Centralized model registry for Project Vyasa.

Provides a single source of truth for model identifiers and basic runtime
metadata without altering runtime behavior. Values are populated from existing
environment-derived defaults in shared.config.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from .config import (
    BRAIN_MODEL_NAME,
    WORKER_MODEL_NAME,
    VISION_MODEL_NAME,
    ARANGODB_DB,
)


@dataclass(frozen=True)
class ModelConfig:
    """Typed model configuration."""

    key: str
    model_id: str
    provider: str
    purpose: str
    default_context: Optional[int] = None
    max_context: Optional[int] = None
    kv_policy: Optional[str] = None
    quantization: Optional[str] = None
    endpoint_env: Optional[str] = None

    def validate(self) -> None:
        """Basic validation to catch misconfiguration early."""
        if not self.model_id:
            raise ValueError(f"Model '{self.key}' is missing a model_id")
        if self.default_context is not None and self.default_context <= 0:
            raise ValueError(f"Model '{self.key}' has invalid default_context: {self.default_context}")
        if self.max_context is not None and self.max_context <= 0:
            raise ValueError(f"Model '{self.key}' has invalid max_context: {self.max_context}")
        if self.default_context and self.max_context and self.default_context > self.max_context:
            raise ValueError(
                f"Model '{self.key}' default_context ({self.default_context}) exceeds max_context ({self.max_context})"
            )


# Registry seeded from existing env-configured defaults; no behavior changes.
_MODEL_REGISTRY: Dict[str, ModelConfig] = {
    "brain": ModelConfig(
        key="brain",
        model_id=BRAIN_MODEL_NAME,
        provider="sglang",
        purpose="critic / high-level reasoning",
        default_context=None,
        max_context=None,
        kv_policy="mem-fraction-static (compose)",
        quantization="mxfp4 (compose)",
        endpoint_env="BRAIN_URL",
    ),
    "worker": ModelConfig(
        key="worker",
        model_id=WORKER_MODEL_NAME,
        provider="sglang",
        purpose="extraction / cartographer",
        default_context=16384,
        max_context=None,
        kv_policy="mem-fraction-static (compose)",
        quantization="fp4 (compose)",
        endpoint_env="WORKER_URL",
    ),
    "vision": ModelConfig(
        key="vision",
        model_id=VISION_MODEL_NAME,
        provider="sglang",
        purpose="vision / OCR",
        default_context=None,
        max_context=None,
        kv_policy="mem-fraction-static (compose)",
        quantization="int8 (compose)",
        endpoint_env="VISION_URL",
    ),
    "embedder": ModelConfig(
        key="embedder",
        model_id="all-MiniLM-L6-v2",
        provider="sentence-transformers",
        purpose="embeddings",
        default_context=None,
        max_context=None,
        kv_policy=None,
        quantization=None,
        endpoint_env="SENTENCE_TRANSFORMER_URL",
    ),
    "drafter": ModelConfig(
        key="drafter",
        model_id="(ollama model not set in repo)",
        provider="ollama",
        purpose="prose / drafting",
        default_context=None,
        max_context=None,
        kv_policy=None,
        quantization=None,
        endpoint_env="DRAFTER_URL",
    ),
}

# Validate at import to fail fast on obvious issues.
for cfg in _MODEL_REGISTRY.values():
    cfg.validate()


def get_model_config(key: str) -> ModelConfig:
    """Fetch a model configuration by key."""
    if key not in _MODEL_REGISTRY:
        raise KeyError(f"Model config not found for key: {key}")
    return _MODEL_REGISTRY[key]


def list_models() -> Dict[str, ModelConfig]:
    """Return the full registry."""
    return _MODEL_REGISTRY.copy()
