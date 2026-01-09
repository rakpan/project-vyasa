"""
Shared configuration for Project Vyasa.

[Configuration Sovereignty] This module is the SINGLE SOURCE OF TRUTH for all system settings.
All code MUST use the getter methods defined here; NO raw os.getenv() calls are allowed in orchestrator nodes.

Centralizes service URLs and connection settings using environment variables.
All services should use these constants instead of hardcoded URLs.
"""

import os
from typing import Optional


def get_checkpoint_saver():
    """Initialize a shared in-memory checkpoint saver for LangGraph.
    
    Returns:
        InMemorySaver instance shared across graph.compile() calls.
    
    Raises:
        RuntimeError if langgraph is unavailable.
    """
    try:
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()
    except Exception as exc:
        raise RuntimeError("LangGraph checkpoint saver unavailable; install langgraph>=0.2.35") from exc


def _env(key: str, default: str = "") -> str:
    """Read environment variable with a default.
    
    Internal helper - use public getter methods instead of calling this directly.
    """
    return os.getenv(key, default)


def get_arango_password() -> str:
    """Canonical ArangoDB password lookup (prefers ARANGO_ROOT_PASSWORD, falls back to legacy).
    
    [Drift Mitigation] Checks both ARANGO_ROOT_PASSWORD (canonical) and ARANGODB_PASSWORD (legacy)
    to handle transition period during migration.
    """
    return os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGODB_PASSWORD", "")


def get_arango_url() -> str:
    """Canonical ArangoDB URL, preferring graph service hostname."""
    return (
        os.getenv("MEMORY_URL")
        or os.getenv("ARANGODB_URL")
        or f"http://graph:{os.getenv('PORT_MEMORY', '8529')}"
    )


def get_vector_url() -> str:
    """Canonical Qdrant URL."""
    return os.getenv("VECTOR_URL") or os.getenv("QDRANT_URL") or "http://vector:6333"


def get_embedder_url() -> str:
    """Canonical embedder URL."""
    return os.getenv("EMBEDDER_URL") or "http://embedder:30010"


def get_reranker_url() -> str:
    """Canonical reranker URL."""
    return os.getenv("RERANKER_URL") or "http://reranker:30011"


def get_orchestrator_url() -> str:
    """Canonical orchestrator URL."""
    return os.getenv("ORCHESTRATOR_URL") or "http://orchestrator:8000"


def get_worker_url() -> str:
    """Canonical worker URL."""
    return os.getenv("WORKER_URL") or os.getenv("CORTEX_WORKER_URL") or "http://cortex-worker:30001"

# ============================================
# Service URLs (from Docker Compose)
# ============================================

# Cortex Services - Committee of Experts Architecture
CORTEX_BRAIN_URL: str = _env("CORTEX_BRAIN_URL", "http://cortex-brain:30000")
BRAIN_URL: str = _env("BRAIN_URL", CORTEX_BRAIN_URL)
CORTEX_WORKER_URL: str = _env("CORTEX_WORKER_URL", "http://cortex-worker:30001")
WORKER_URL: str = _env("WORKER_URL", CORTEX_WORKER_URL)
CORTEX_VISION_URL: str = _env("CORTEX_VISION_URL", "http://cortex-vision:30002")
VISION_URL: str = _env("VISION_URL", CORTEX_VISION_URL)

# ============================================
# Canonical Model Configuration (Consolidated)
# ============================================
# Use TEXT_MODEL_ID, VISION_MODEL_ID, EMBEDDER_MODEL_ID for all model configuration.
# Legacy vars (BRAIN_MODEL_PATH, WORKER_MODEL_PATH, etc.) are supported for one release with deprecation warnings.

# Text model (used by both Brain and Worker services)
# Default: nvidia/Llama-3_3-Nemotron-Super-49B-v1_5 (DGX Spark optimized)
TEXT_MODEL_ID: str = _env(
    "TEXT_MODEL_ID",
    _env("BRAIN_MODEL_PATH", _env("WORKER_MODEL_PATH", "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5"))
)

# Vision model (used by Vision service)
# Default: Qwen/Qwen2-VL-7B-Instruct (target consolidation model)
VISION_MODEL_ID: str = _env(
    "VISION_MODEL_ID",
    _env("VISION_MODEL_PATH", "Qwen/Qwen2-VL-7B-Instruct")
)

# Embedder model (used by Embedder service)
# Default: nvidia/nv-embedqa-e5-v5 (target consolidation model)
# Note: EMBEDDING_MODEL_PATH is checked as fallback for backward compatibility
_embedding_model_path_fallback = os.getenv("EMBEDDING_MODEL_PATH")
EMBEDDER_MODEL_ID: str = _env(
    "EMBEDDER_MODEL_ID",
    _embedding_model_path_fallback if _embedding_model_path_fallback else "nvidia/nv-embedqa-e5-v5"
)

# Reranker model (used by Reranker service)
# Default: nvidia/llama-3.2-nv-rerankqa-1b-v2 (NeMo Retriever Text Reranking NIM)
RERANKER_MODEL_ID: str = _env(
    "RERANKER_MODEL_ID",
    "nvidia/llama-3.2-nv-rerankqa-1b-v2"
)

# Backward compatibility: Emit deprecation warnings if legacy vars are used
# Only warn if legacy var is set AND canonical var is NOT set (user is relying on legacy)
import warnings
if os.getenv("BRAIN_MODEL_PATH") and not os.getenv("TEXT_MODEL_ID"):
    warnings.warn(
        "BRAIN_MODEL_PATH is deprecated. Use TEXT_MODEL_ID instead. "
        "BRAIN_MODEL_PATH will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2
    )
if os.getenv("WORKER_MODEL_PATH") and not os.getenv("TEXT_MODEL_ID"):
    warnings.warn(
        "WORKER_MODEL_PATH is deprecated. Use TEXT_MODEL_ID instead. "
        "WORKER_MODEL_PATH will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2
    )
if os.getenv("VISION_MODEL_PATH") and not os.getenv("VISION_MODEL_ID"):
    warnings.warn(
        "VISION_MODEL_PATH is deprecated. Use VISION_MODEL_ID instead. "
        "VISION_MODEL_PATH will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2
    )
if os.getenv("EMBEDDING_MODEL_PATH") and not os.getenv("EMBEDDER_MODEL_ID"):
    warnings.warn(
        "EMBEDDING_MODEL_PATH is deprecated. Use EMBEDDER_MODEL_ID instead. "
        "EMBEDDING_MODEL_PATH will be removed in a future release.",
        DeprecationWarning,
        stacklevel=2
    )

# Legacy aliases for backward compatibility (one release)
BRAIN_MODEL_PATH: str = TEXT_MODEL_ID  # type: ignore[misc,assignment]
BRAIN_MODEL_NAME: str = TEXT_MODEL_ID  # type: ignore[misc,assignment]
WORKER_MODEL_PATH: str = TEXT_MODEL_ID  # type: ignore[misc,assignment]
WORKER_MODEL_NAME: str = TEXT_MODEL_ID  # type: ignore[misc,assignment]
VISION_MODEL_PATH: str = VISION_MODEL_ID  # type: ignore[misc,assignment]
VISION_MODEL_NAME: str = VISION_MODEL_ID  # type: ignore[misc,assignment]
EMBEDDING_MODEL_PATH: str = EMBEDDER_MODEL_ID  # type: ignore[misc,assignment]

# Legacy aliases for backward compatibility
CORTEX_URL: str = _env("CORTEX_URL", CORTEX_BRAIN_URL)
CORTEX_SERVICE_URL: str = _env("CORTEX_SERVICE_URL", CORTEX_URL)

# Legacy worker URL (optional alias for backward compatibility)
LEGACY_WORKER_URL: str = _env("LEGACY_WORKER_URL", WORKER_URL)  # Optional alias for legacy configs

# Memory (ArangoDB) - Knowledge Graph
MEMORY_URL: str = get_arango_url()
MEMORY_SERVICE_URL: str = MEMORY_URL  # Alias
ARANGODB_URL: str = MEMORY_URL  # Alias

# Vector (Qdrant) - Search Index
VECTOR_URL: str = get_vector_url()
QDRANT_URL: str = VECTOR_URL  # Alias

# Embedder (Sentence Transformers) - Vectorizer
EMBEDDER_URL: str = get_embedder_url()
SENTENCE_TRANSFORMER_URL: str = EMBEDDER_URL  # Alias
# Embedding model path (HuggingFace Hub format) - legacy alias, use EMBEDDER_MODEL_ID
EMBEDDING_MODEL_PATH: str = EMBEDDER_MODEL_ID  # type: ignore[misc,assignment]
# Embedding dimension (nv-embedqa-e5-v5 = 1024)
# This must match the embedding model's output dimension
EMBEDDING_DIMENSION: int = int(_env("EMBEDDING_DIMENSION", "1024"))
# HuggingFace Hub token for authenticated model downloads
HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")

# Reranker (NeMo Retriever Text Reranking NIM) - Relevance Scorer
RERANKER_URL: str = get_reranker_url()

# Reranker configuration (feature flags)
RERANKER_ENABLED: bool = _env("RERANKER_ENABLED", "true").lower() in ("true", "1", "yes")
RERANKER_REQUIRED: bool = _env("RERANKER_REQUIRED", "false").lower() in ("true", "1", "yes")

# Retrieval configuration (defaults for section loop)
RETRIEVAL_TOP_K: int = int(_env("RETRIEVAL_TOP_K", "64"))  # Top-K from Qdrant (before reranking)
RERANK_TOP_M: int = int(_env("RERANK_TOP_M", "24"))  # Top-M after reranking

# ============================================
# Local Paths (DGX / RAID defaults)
# ============================================
RAID_BASE: str = _env("RAID_BASE", "/raid/vyasa")
MODEL_CACHE_DIR: str = _env("MODEL_CACHE_DIR", os.path.join(RAID_BASE, "model_cache"))
SCRATCH_DIR: str = _env("SCRATCH_DIR", os.path.join(RAID_BASE, "scratch"))
TELEMETRY_PATH: str = _env("TELEMETRY_PATH", os.path.join(RAID_BASE, "telemetry", "events.jsonl"))
HF_HOME_DIR: str = _env("HF_HOME", os.path.join(RAID_BASE, "hf_cache"))

# ============================================
# Context / Concurrency Policies
# ============================================
CONTEXT_LIMITS = {
    "WORKER": int(_env("CONTEXT_LIMIT_WORKER", "16384")),
    "BRAIN": int(_env("CONTEXT_LIMIT_BRAIN", "32768")),
    "LOGICIAN": int(_env("CONTEXT_LIMIT_LOGICIAN", "64536")),  # Burst only
}

MAX_CONCURRENCY = {
    "WORKER": int(_env("MAX_CONCURRENCY_WORKER", "8")),
    "BRAIN": int(_env("MAX_CONCURRENCY_BRAIN", "2")),
    "VISION": int(_env("MAX_CONCURRENCY_VISION", "2")),
}

# ============================================
# Opik (Observe-only tracing)
# ============================================
OPIK_ENABLED: bool = _env("OPIK_ENABLED", "false").lower() in ("true", "1", "yes")
OPIK_BASE_URL: Optional[str] = os.getenv("OPIK_BASE_URL")
OPIK_API_KEY: Optional[str] = os.getenv("OPIK_API_KEY")
OPIK_PROJECT_NAME: str = _env("OPIK_PROJECT_NAME", "vyasa")
OPIK_TIMEOUT_SECONDS: int = int(_env("OPIK_TIMEOUT_SECONDS", "2"))

# Prompt Registry Configuration
PROMPT_REGISTRY_ENABLED: bool = _env("PROMPT_REGISTRY_ENABLED", "").lower() in ("true", "1", "yes") or OPIK_ENABLED
PROMPT_CACHE_SECONDS: int = int(_env("PROMPT_CACHE_SECONDS", "300"))  # Default 5 minutes
PROMPT_TAG: str = _env("PROMPT_TAG", "production")  # Default tag for prompt versions

# ============================================
# Timeout Matrix (seconds)
# ============================================
TIMEOUT_MATRIX = {
    "SGLANG_CALL": int(_env("TIMEOUT_SGLANG_CALL", "60")),
    "ARANGO_QUERY": int(_env("TIMEOUT_ARANGO_QUERY", "15")),
    "OOB_SIDELOAD": int(_env("TIMEOUT_OOB_SIDELOAD", "30")),
}

# ============================================
# Database Configuration
# ============================================

ARANGODB_DB: str = _env("ARANGODB_DB", "project_vyasa")
ARANGODB_USER: str = _env("ARANGODB_USER", "root")
ARANGODB_PASSWORD: str = _env("ARANGODB_PASSWORD", "")

# ============================================
# Runtime Safeguards
# ============================================
MAX_KV_CACHE_GB: int = int(_env("MAX_KV_CACHE_GB", "30"))
# Optional per-service caps (can be tuned in deploy/.env)
MAX_KV_CACHE_GB_BRAIN: int = int(_env("MAX_KV_CACHE_GB_BRAIN", str(MAX_KV_CACHE_GB)))
MAX_KV_CACHE_GB_WORKER: int = int(_env("MAX_KV_CACHE_GB_WORKER", str(MAX_KV_CACHE_GB)))

# ============================================
# Out-of-Band (OOB) Research Ingestion
# ============================================
# Confidence threshold for automatic promotion of candidate facts to canonical knowledge
OOB_PROMOTION_CONFIDENCE_THRESHOLD: float = float(_env("OOB_PROMOTION_CONFIDENCE_THRESHOLD", "0.85"))
# Require source_url for automatic promotion (prevents promotion of unverified sources)
OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION: bool = _env("OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION", "true").lower() in ("true", "1", "yes")

# ============================================
# Environment Variable Names (for reference)
# ============================================
# These can be set in docker-compose.yml or .env files:
#
# CORTEX_URL=http://cortex-brain:30000
# MEMORY_URL=http://graph:8529
# VECTOR_URL=http://vector:6333
# EMBEDDER_URL=http://embedder:30010
#
# ARANGODB_DB=project_vyasa
# ARANGODB_USER=root
# ARANGODB_PASSWORD=

# ============================================
# Helper Functions
# ============================================

def get_cortex_url() -> str:
    """Get Cortex service URL from environment or default (legacy - returns Brain)."""
    return CORTEX_SERVICE_URL

def get_brain_url() -> str:
    """Get Brain (Logic) service URL from environment or default."""
    return BRAIN_URL

def get_worker_url() -> str:
    """Get Worker (Extraction) service URL from environment or default."""
    return WORKER_URL

def get_vision_url() -> str:
    """Get Vision (Eye) service URL from environment or default."""
    return VISION_URL

# Vision as optional accelerator configuration
# Vision is disabled by default for journals-first system (most PDFs are text-based)
VISION_ENABLED: bool = _env("VISION_ENABLED", "false").lower() in ("true", "1", "yes")
VISION_TRIAGE_PAGES: int = int(_env("VISION_TRIAGE_PAGES", "2"))  # Number of pages to preview for triage
VISION_MIN_TEXT_CHARS: int = int(_env("VISION_MIN_TEXT_CHARS", "800"))  # Minimum text chars to consider PDF text-based
VISION_HEALTH_TIMEOUT: float = float(_env("VISION_HEALTH_TIMEOUT", "1.0"))  # Health check timeout in seconds

def get_memory_url() -> str:
    """Get Memory (ArangoDB) service URL from environment or default."""
    return MEMORY_URL

def get_embedding_device() -> str:
    """Get the device to use for embedding models.
    
    Returns "cuda" if GPU is available, otherwise "cpu".
    """
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        # torch not available, default to cpu
        return "cpu"


def get_artifact_root() -> str:
    """Get artifact root directory path."""
    return _env("ARTIFACT_ROOT", "/raid/artifacts")


def get_dataset_dir() -> str:
    """Get knowledge harvester dataset directory path."""
    return _env("VYASA_DATASET_DIR", "/raid/datasets")
