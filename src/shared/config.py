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
# Brain (Logic) - High-level reasoning and JSON planning
CORTEX_BRAIN_URL: str = _env("CORTEX_BRAIN_URL", "http://cortex-brain:30000")
BRAIN_URL: str = _env("BRAIN_URL", CORTEX_BRAIN_URL)
BRAIN_MODEL_NAME: str = _env("BRAIN_MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")

# Worker (Extraction) - Strict JSON extraction (cheap model)
CORTEX_WORKER_URL: str = _env("CORTEX_WORKER_URL", "http://cortex-worker:30001")
WORKER_URL: str = _env("WORKER_URL", CORTEX_WORKER_URL)
# Worker (Extraction) - Qwen 2.5 49B model path
# Note: Default HuggingFace path uses legacy naming; override via WORKER_MODEL_NAME env var
WORKER_MODEL_NAME: str = _env("WORKER_MODEL_NAME", "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5")

# Vision (Eye) - Description and data point extraction
CORTEX_VISION_URL: str = _env("CORTEX_VISION_URL", "http://cortex-vision:30002")
VISION_URL: str = _env("VISION_URL", CORTEX_VISION_URL)
VISION_MODEL_NAME: str = _env("VISION_MODEL_NAME", "Qwen/Qwen2-VL-72B-Instruct")

# Legacy aliases for backward compatibility
CORTEX_URL: str = _env("CORTEX_URL", CORTEX_BRAIN_URL)
CORTEX_SERVICE_URL: str = _env("CORTEX_SERVICE_URL", CORTEX_URL)

# Drafter (Ollama) - Chat & Prose
DRAFTER_URL: str = _env("DRAFTER_URL", "http://drafter:11435")
LEGACY_WORKER_URL: str = _env("LEGACY_WORKER_URL", DRAFTER_URL)  # Optional alias for legacy configs

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
# Embedding model path (HuggingFace Hub format)
EMBEDDING_MODEL_PATH: str = _env("EMBEDDING_MODEL_PATH", "BAAI/bge-large-en-v1.5")
# Embedding dimension (BGE-Large = 1024)
EMBEDDING_DIMENSION: int = int(_env("EMBEDDING_DIMENSION", "1024"))
# HuggingFace Hub token for authenticated model downloads
HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")

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
# DRAFTER_URL=http://drafter:11435
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

def get_drafter_url() -> str:
    """Get Drafter service URL from environment or default."""
    return DRAFTER_URL

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
