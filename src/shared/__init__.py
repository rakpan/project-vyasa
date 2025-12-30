"""Shared schemas and models for Project Vyasa."""

from .schema import (
    Vulnerability,
    Mechanism,
    Constraint,
    Outcome,
    Entity,
    GraphTriple,
    KnowledgeGraph,
    RelationType,
    EntityType,
    ManuscriptBlock,
    PatchObject,
)
# Backward compatibility alias (deprecated)
PACTGraph = KnowledgeGraph
from .config import (
    CORTEX_URL,
    CORTEX_SERVICE_URL,
    DRAFTER_URL,
    WORKER_URL,
    MEMORY_URL,
    MEMORY_SERVICE_URL,
    ARANGODB_URL,
    VECTOR_URL,
    QDRANT_URL,
    EMBEDDER_URL,
    SENTENCE_TRANSFORMER_URL,
    ARANGODB_DB,
    ARANGODB_USER,
    ARANGODB_PASSWORD,
    get_cortex_url,
    get_drafter_url,
    get_memory_url,
    get_vector_url,
    get_embedder_url,
)

__all__ = [
    # Schema exports
    "Vulnerability",
    "Mechanism",
    "Constraint",
    "Outcome",
    "Entity",
    "GraphTriple",
    "KnowledgeGraph",
    "PACTGraph",  # Deprecated alias
    "RelationType",
    "EntityType",
    "ManuscriptBlock",
    "PatchObject",
    # Config exports
    "CORTEX_URL",
    "CORTEX_SERVICE_URL",
    "DRAFTER_URL",
    "WORKER_URL",
    "MEMORY_URL",
    "MEMORY_SERVICE_URL",
    "ARANGODB_URL",
    "VECTOR_URL",
    "QDRANT_URL",
    "EMBEDDER_URL",
    "SENTENCE_TRANSFORMER_URL",
    "ARANGODB_DB",
    "ARANGODB_USER",
    "ARANGODB_PASSWORD",
    "get_cortex_url",
    "get_drafter_url",
    "get_memory_url",
    "get_vector_url",
    "get_embedder_url",
]

