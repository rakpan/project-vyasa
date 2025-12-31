"""
Shared configuration for Project Vyasa.

Centralizes service URLs and connection settings using environment variables.
All services should use these constants instead of hardcoded URLs.
"""

import os
from typing import Optional

# ============================================
# Service URLs (from Docker Compose)
# ============================================

# Cortex Services - Committee of Experts Architecture
# Brain (Logic) - High-level reasoning and JSON planning
CORTEX_BRAIN_URL: str = os.getenv("CORTEX_BRAIN_URL", "http://cortex-brain:30000")
BRAIN_URL: str = os.getenv("BRAIN_URL", CORTEX_BRAIN_URL)
BRAIN_MODEL_NAME: str = os.getenv("BRAIN_MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")

# Worker (Extraction) - Strict JSON extraction (cheap model)
CORTEX_WORKER_URL: str = os.getenv("CORTEX_WORKER_URL", "http://cortex-worker:30001")
WORKER_URL: str = os.getenv("WORKER_URL", CORTEX_WORKER_URL)
# Worker (Extraction) - Qwen 2.5 49B model path
# Note: Default HuggingFace path uses legacy naming; override via WORKER_MODEL_NAME env var
WORKER_MODEL_NAME: str = os.getenv("WORKER_MODEL_NAME", "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5")

# Vision (Eye) - Description and data point extraction
CORTEX_VISION_URL: str = os.getenv("CORTEX_VISION_URL", "http://cortex-vision:30002")
VISION_URL: str = os.getenv("VISION_URL", CORTEX_VISION_URL)
VISION_MODEL_NAME: str = os.getenv("VISION_MODEL_NAME", "Qwen/Qwen2-VL-72B-Instruct")

# Legacy aliases for backward compatibility
CORTEX_URL: str = os.getenv("CORTEX_URL", CORTEX_BRAIN_URL)
CORTEX_SERVICE_URL: str = os.getenv("CORTEX_SERVICE_URL", CORTEX_URL)

# Drafter (Ollama) - Chat & Prose
DRAFTER_URL: str = os.getenv("DRAFTER_URL", "http://vyasa-drafter:11434")
LEGACY_WORKER_URL: str = os.getenv("LEGACY_WORKER_URL", DRAFTER_URL)  # Optional alias for legacy configs

# Memory (ArangoDB) - Knowledge Graph
MEMORY_URL: str = os.getenv("MEMORY_URL", "http://vyasa-memory:8529")
MEMORY_SERVICE_URL: str = os.getenv("MEMORY_SERVICE_URL", MEMORY_URL)  # Alias
ARANGODB_URL: str = os.getenv("ARANGODB_URL", MEMORY_URL)  # Alias

# Vector (Qdrant) - Search Index
VECTOR_URL: str = os.getenv("VECTOR_URL", "http://vyasa-qdrant:6333")
QDRANT_URL: str = os.getenv("QDRANT_URL", VECTOR_URL)  # Alias

# Embedder (Sentence Transformers) - Vectorizer
EMBEDDER_URL: str = os.getenv("EMBEDDER_URL", "http://vyasa-embedder:80")
SENTENCE_TRANSFORMER_URL: str = os.getenv("SENTENCE_TRANSFORMER_URL", EMBEDDER_URL)  # Alias
# Embedding model path (HuggingFace Hub format)
EMBEDDING_MODEL_PATH: str = os.getenv("EMBEDDING_MODEL_PATH", "BAAI/bge-large-en-v1.5")
# Embedding dimension (BGE-Large = 1024)
EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
# HuggingFace Hub token for authenticated model downloads
HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")

# ============================================
# Local Paths (DGX / RAID defaults)
# ============================================
RAID_BASE: str = os.getenv("RAID_BASE", "/raid/vyasa")
MODEL_CACHE_DIR: str = os.getenv("MODEL_CACHE_DIR", os.path.join(RAID_BASE, "model_cache"))
SCRATCH_DIR: str = os.getenv("SCRATCH_DIR", os.path.join(RAID_BASE, "scratch"))
TELEMETRY_PATH: str = os.getenv("TELEMETRY_PATH", os.path.join(RAID_BASE, "telemetry", "events.jsonl"))
HF_HOME_DIR: str = os.getenv("HF_HOME", os.path.join(RAID_BASE, "hf_cache"))

# ============================================
# Context / Concurrency Policies
# ============================================
CONTEXT_LIMITS = {
    "WORKER": int(os.getenv("CONTEXT_LIMIT_WORKER", "16384")),
    "BRAIN": int(os.getenv("CONTEXT_LIMIT_BRAIN", "32768")),
    "LOGICIAN": int(os.getenv("CONTEXT_LIMIT_LOGICIAN", "64536")),  # Burst only
}

MAX_CONCURRENCY = {
    "WORKER": int(os.getenv("MAX_CONCURRENCY_WORKER", "8")),
    "BRAIN": int(os.getenv("MAX_CONCURRENCY_BRAIN", "2")),
    "VISION": int(os.getenv("MAX_CONCURRENCY_VISION", "2")),
}

# ============================================
# Opik (Observe-only tracing)
# ============================================
OPIK_ENABLED: bool = os.getenv("OPIK_ENABLED", "false").lower() in ("true", "1", "yes")
OPIK_BASE_URL: Optional[str] = os.getenv("OPIK_BASE_URL")
OPIK_API_KEY: Optional[str] = os.getenv("OPIK_API_KEY")
OPIK_PROJECT_NAME: str = os.getenv("OPIK_PROJECT_NAME", "vyasa")
OPIK_TIMEOUT_SECONDS: int = int(os.getenv("OPIK_TIMEOUT_SECONDS", "2"))

# ============================================
# Timeout Matrix (seconds)
# ============================================
TIMEOUT_MATRIX = {
    "SGLANG_CALL": int(os.getenv("TIMEOUT_SGLANG_CALL", "60")),
    "ARANGO_QUERY": int(os.getenv("TIMEOUT_ARANGO_QUERY", "15")),
    "OOB_SIDELOAD": int(os.getenv("TIMEOUT_OOB_SIDELOAD", "30")),
}

# ============================================
# Database Configuration
# ============================================

ARANGODB_DB: str = os.getenv("ARANGODB_DB", "project_vyasa")
ARANGODB_USER: str = os.getenv("ARANGODB_USER", "root")
ARANGODB_PASSWORD: str = os.getenv("ARANGODB_PASSWORD", "")

# ============================================
# Runtime Safeguards
# ============================================
MAX_KV_CACHE_GB: int = int(os.getenv("MAX_KV_CACHE_GB", "30"))
# Optional per-service caps (can be tuned in deploy/.env)
MAX_KV_CACHE_GB_BRAIN: int = int(os.getenv("MAX_KV_CACHE_GB_BRAIN", str(MAX_KV_CACHE_GB)))
MAX_KV_CACHE_GB_WORKER: int = int(os.getenv("MAX_KV_CACHE_GB_WORKER", str(MAX_KV_CACHE_GB)))

# ============================================
# Out-of-Band (OOB) Research Ingestion
# ============================================
# Confidence threshold for automatic promotion of candidate facts to canonical knowledge
OOB_PROMOTION_CONFIDENCE_THRESHOLD: float = float(os.getenv("OOB_PROMOTION_CONFIDENCE_THRESHOLD", "0.85"))
# Require source_url for automatic promotion (prevents promotion of unverified sources)
OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION: bool = os.getenv("OOB_REQUIRE_SOURCE_URL_FOR_AUTO_PROMOTION", "true").lower() in ("true", "1", "yes")

# ============================================
# Environment Variable Names (for reference)
# ============================================
# These can be set in docker-compose.yml or .env files:
#
# CORTEX_URL=http://vyasa-cortex:30000
# DRAFTER_URL=http://vyasa-drafter:11434
# MEMORY_URL=http://vyasa-memory:8529
# VECTOR_URL=http://vyasa-qdrant:6333
# EMBEDDER_URL=http://vyasa-embedder:80
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

def get_arango_password() -> str:
    """Centralized ArangoDB password lookup with ARANGO_ROOT_PASSWORD override."""
    return os.getenv("ARANGO_ROOT_PASSWORD") or ARANGODB_PASSWORD

def get_vector_url() -> str:
    """Get Vector (Qdrant) service URL from environment or default."""
    return VECTOR_URL

def get_embedder_url() -> str:
    """Get Embedder service URL from environment or default."""
    return EMBEDDER_URL


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
