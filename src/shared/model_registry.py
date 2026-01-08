"""
Centralized model registry for Project Vyasa.

Provides a single source of truth for model identifiers and basic runtime
metadata without altering runtime behavior. Values are populated from existing
environment-derived defaults in shared.config.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from .config import (
    TEXT_MODEL_ID,
    VISION_MODEL_ID,
    EMBEDDER_MODEL_ID,
    ARANGODB_DB,
)


@dataclass(frozen=True)
class ModelConfig:
    """Typed model configuration.
    
    The registry is authoritative for:
    - model_id: Which model to load (HuggingFace path or local path)
    - purpose: Semantic purpose of the model
    - provider: Runtime provider (sglang, ollama, sentence-transformers)
    - endpoint_env: Which service endpoint to call
    
    The registry is NOT authoritative for deployment optimizations:
    - quantization, kv_policy: These are deployment hints only (non-authoritative)
      Actual values are configured in deploy/docker-compose.yml command flags
    - default_context, max_context: These are hints only (non-authoritative)
      Actual context limits are configured in deploy/docker-compose.yml
    """

    key: str
    model_id: str  # Authoritative: which model to load
    provider: str  # Authoritative: runtime provider
    purpose: str  # Authoritative: semantic purpose
    default_context: Optional[int] = None  # Non-authoritative: deployment hint only
    max_context: Optional[int] = None  # Non-authoritative: deployment hint only
    kv_policy: Optional[str] = None  # Non-authoritative: deployment hint only (see docker-compose.yml)
    quantization: Optional[str] = None  # Non-authoritative: deployment hint only (see docker-compose.yml)
    endpoint_env: Optional[str] = None  # Authoritative: which endpoint to call

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


# Registry uses canonical model IDs: TEXT_MODEL_ID, VISION_MODEL_ID, EMBEDDER_MODEL_ID
# Both Brain and Worker use TEXT_MODEL_ID (same model, different services for redundancy)
_MODEL_REGISTRY: Dict[str, ModelConfig] = {
    "brain": ModelConfig(
        key="brain",
        model_id=TEXT_MODEL_ID,  # Uses canonical TEXT_MODEL_ID
        provider="sglang",
        purpose="critic / high-level reasoning",
        default_context=None,
        max_context=None,
        kv_policy="mem-fraction-static (compose)",  # Non-authoritative: actual value in docker-compose.yml
        quantization="int8 (compose)",  # Non-authoritative: actual value in docker-compose.yml
        endpoint_env="BRAIN_URL",
    ),
    "worker": ModelConfig(
        key="worker",
        model_id=TEXT_MODEL_ID,  # Uses canonical TEXT_MODEL_ID (same as Brain)
        provider="sglang",
        purpose="extraction / cartographer",
        default_context=16384,  # Non-authoritative: actual value in docker-compose.yml --context-length flag
        max_context=None,
        kv_policy="mem-fraction-static (compose)",
        quantization="fp4 (compose)",
        endpoint_env="WORKER_URL",
    ),
    "vision": ModelConfig(
        key="vision",
        model_id=VISION_MODEL_ID,  # Uses canonical VISION_MODEL_ID
        provider="sglang",
        purpose="vision / OCR",
        default_context=None,
        max_context=None,
        kv_policy="mem-fraction-static (compose)",  # Non-authoritative: actual value in docker-compose.yml
        quantization="int8 (compose)",  # Non-authoritative: actual value in docker-compose.yml
        endpoint_env="VISION_URL",
    ),
    "embedder": ModelConfig(
        key="embedder",
        model_id=EMBEDDER_MODEL_ID,  # Uses canonical EMBEDDER_MODEL_ID (removed hardcoded all-MiniLM-L6-v2)
        provider="sentence-transformers",
        purpose="embeddings",
        default_context=None,
        max_context=None,
        kv_policy=None,
        quantization=None,
        endpoint_env="SENTENCE_TRANSFORMER_URL",
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
