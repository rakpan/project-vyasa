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

# Worker (Extraction) - Strict JSON extraction (cheap model)
CORTEX_WORKER_URL: str = os.getenv("CORTEX_WORKER_URL", "http://cortex-worker:30001")
WORKER_URL: str = os.getenv("WORKER_URL", CORTEX_WORKER_URL)

# Vision (Eye) - Description and data point extraction
CORTEX_VISION_URL: str = os.getenv("CORTEX_VISION_URL", "http://cortex-vision:30002")
VISION_URL: str = os.getenv("VISION_URL", CORTEX_VISION_URL)

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

# ============================================
# Database Configuration
# ============================================

ARANGODB_DB: str = os.getenv("ARANGODB_DB", "project_vyasa")
ARANGODB_USER: str = os.getenv("ARANGODB_USER", "root")
ARANGODB_PASSWORD: str = os.getenv("ARANGODB_PASSWORD", "")

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

def get_vector_url() -> str:
    """Get Vector (Qdrant) service URL from environment or default."""
    return VECTOR_URL

def get_embedder_url() -> str:
    """Get Embedder service URL from environment or default."""
    return EMBEDDER_URL
