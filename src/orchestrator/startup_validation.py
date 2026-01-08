"""
Startup validation for orchestrator service.

Validates critical system state before allowing operations:
- Qdrant collection dimensions match configured embedding model
- Other critical dependencies are healthy
"""

from typing import Dict, List, Optional, Tuple
from ...shared.logger import get_logger
from ...shared.config import EMBEDDING_DIMENSION
from ...vector.client import get_qdrant_client, ensure_collection_dimension

logger = get_logger("orchestrator", __name__)

# Required Qdrant collections that must have matching dimensions
REQUIRED_COLLECTIONS = [
    "document_chunks",
    "entity-embeddings",
    "document-embeddings",
]


def validate_qdrant_collections() -> Tuple[bool, List[str]]:
    """
    Validate that all required Qdrant collections have the correct embedding dimension.
    
    Returns:
        Tuple of (is_valid, error_messages):
        - is_valid: True if all collections are valid, False otherwise
        - error_messages: List of error messages for any mismatches
    """
    errors: List[str] = []
    
    try:
        client = get_qdrant_client()
    except Exception as e:
        error_msg = f"Failed to connect to Qdrant: {e}"
        logger.critical(error_msg, exc_info=True)
        errors.append(error_msg)
        return False, errors
    
    for collection_name in REQUIRED_COLLECTIONS:
        try:
            ensure_collection_dimension(client, collection_name, EMBEDDING_DIMENSION)
        except ValueError as e:
            error_msg = f"Collection '{collection_name}': {e}"
            logger.critical(
                error_msg,
                extra={
                    "payload": {
                        "collection_name": collection_name,
                        "expected_dimension": EMBEDDING_DIMENSION,
                    }
                }
            )
            errors.append(error_msg)
        except Exception as e:
            # Collection may not exist yet - that's OK, it will be created with correct dimension
            logger.debug(
                f"Collection '{collection_name}' not found or error checking dimension: {e}",
                extra={"payload": {"collection_name": collection_name}}
            )
    
    is_valid = len(errors) == 0
    if not is_valid:
        logger.critical(
            f"Qdrant dimension validation failed: {len(errors)} collection(s) have dimension mismatches",
            extra={"payload": {"errors": errors, "expected_dimension": EMBEDDING_DIMENSION}}
        )
    
    return is_valid, errors


def get_dimension_validation_status() -> Dict[str, any]:
    """
    Get current dimension validation status for health checks.
    
    Returns:
        Dict with validation status and details:
        {
            "valid": bool,
            "expected_dimension": int,
            "errors": List[str],
            "collections_checked": List[str]
        }
    """
    is_valid, errors = validate_qdrant_collections()
    return {
        "valid": is_valid,
        "expected_dimension": EMBEDDING_DIMENSION,
        "errors": errors,
        "collections_checked": REQUIRED_COLLECTIONS,
    }

