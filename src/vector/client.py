"""
Vector client with dimension guardrails for Qdrant/Arango-backed collections.
"""

from __future__ import annotations

import os
from typing import Optional

from qdrant_client import QdrantClient

from ..shared.config import EMBEDDING_DIMENSION, QDRANT_URL


def get_qdrant_client(url: Optional[str] = None, api_key: Optional[str] = None) -> QdrantClient:
    """Instantiate a Qdrant client using env defaults."""
    target_url = url or QDRANT_URL
    key = api_key or os.getenv("QDRANT_API_KEY")
    return QdrantClient(url=target_url, api_key=key)


def ensure_collection_dimension(client: QdrantClient, collection_name: str, expected_dim: int = EMBEDDING_DIMENSION) -> None:
    """
    Validate that an existing collection matches the expected embedding dimension.

    Raises:
        ValueError: if a dimension mismatch is detected.
    """
    try:
        info = client.get_collection(collection_name)
    except Exception:
        # Collection does not exist or cannot be fetched; create path will handle later
        return

    actual_dim = None
    try:
        actual_dim = info.config.params.vectors.size  # type: ignore[attr-defined]
    except Exception:
        pass

    if actual_dim is not None and actual_dim != expected_dim:
        raise ValueError(
            f"Dimension mismatch detected (existing={actual_dim}, expected={expected_dim}). "
            "Run 'scripts/reindex_corpus.sh' to migrate to the new model."
        )
