"""
ArangoDB storage utilities for ingestion ledger updates and claim loading.

Provides deterministic updates to ingestion records after Qdrant indexing
and functions to load claims from ArangoDB for conflict detection.
"""

from typing import Optional, Dict, Any, List
from arango.database import StandardDatabase

from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

INGESTION_COLLECTION = "ingestions"


def update_ingestion_after_qdrant_indexing(
    db: StandardDatabase,
    ingestion_id: str,
    chunk_count: int,
) -> bool:
    """Update Arango ingestion record after Qdrant indexing completes.
    
    Args:
        db: ArangoDB database instance.
        ingestion_id: Ingestion identifier.
        chunk_count: Number of chunks indexed in Qdrant.
    
    Returns:
        True if updated, False if not found.
    """
    try:
        from ..ingestion_store import IngestionStore, IngestionStatus
        
        ingestion_store = IngestionStore(db)
        from datetime import datetime, timezone
        return ingestion_store.update_ingestion(
            ingestion_id,
            status=IngestionStatus.INDEXED,
            chunk_count=chunk_count,
            indexed_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to update ingestion {ingestion_id} after Qdrant indexing: {e}", exc_info=True)
        return False


def load_claims_for_conflict_detection(
    db: StandardDatabase,
    project_id: str,
    ingestion_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load claims from ArangoDB for deterministic conflict detection.
    
    Queries the extractions collection to retrieve all claims (triples) for
    a given project, optionally filtered by ingestion_id or job_id.
    
    Args:
        db: ArangoDB database instance.
        project_id: Project ID to filter by.
        ingestion_id: Optional ingestion ID to filter by.
        job_id: Optional job ID to filter by.
    
    Returns:
        List of claim dictionaries with:
        - claim_id (or generated from triple)
        - subject, predicate, object
        - source_anchor or source_pointer
        - file_hash, ingestion_id, job_id
        - claim_text (if available)
    """
    claims = []
    
    if not db.has_collection("extractions"):
        logger.warning("extractions collection not found in ArangoDB")
        return claims
    
    try:
        # Build AQL query to find claims/triples
        query = """
        FOR e IN extractions
        FILTER e.project_id == @project_id
        """
        
        bind_vars = {"project_id": project_id}
        
        # Add optional filters
        if ingestion_id:
            query += " FILTER e.ingestion_id == @ingestion_id"
            bind_vars["ingestion_id"] = ingestion_id
        
        if job_id:
            query += " FILTER e._key == @job_id"
            bind_vars["job_id"] = job_id
        
        query += """
        FOR triple IN e.graph.triples
        RETURN {
            claim_id: triple.claim_id,
            subject: triple.subject,
            predicate: triple.predicate,
            object: triple.object,
            confidence: triple.confidence,
            source_anchor: triple.source_anchor,
            source_pointer: triple.source_pointer,
            file_hash: triple.file_hash,
            claim_text: triple.claim_text,
            ingestion_id: e.ingestion_id,
            job_id: e._key,
            project_id: e.project_id
        }
        """
        
        cursor = db.aql.execute(query, bind_vars=bind_vars)
        results = list(cursor)
        
        # Generate claim_id if missing
        for claim in results:
            if not claim.get("claim_id"):
                # Generate deterministic claim_id from triple + source
                from ..schemas.claims import Claim
                file_hash = claim.get("file_hash") or (claim.get("source_pointer") or {}).get("doc_hash", "")
                page_number = (claim.get("source_pointer") or {}).get("page") or (claim.get("source_anchor") or {}).get("page_number", 1)
                claim["claim_id"] = Claim.generate_claim_id(
                    claim.get("subject", ""),
                    claim.get("predicate", ""),
                    claim.get("object", ""),
                    file_hash,
                    page_number,
                )
        
        logger.debug(
            f"Loaded {len(results)} claims for conflict detection",
            extra={"payload": {"project_id": project_id, "ingestion_id": ingestion_id, "job_id": job_id}}
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to load claims for conflict detection: {e}", exc_info=True)
        return []


def get_claim_anchor(
    db: StandardDatabase,
    claim_id: str,
) -> Optional[Dict[str, Any]]:
    """Get source anchor for a claim by claim_id.
    
    Queries the extractions collection to find the claim and return its source_anchor.
    
    Args:
        db: ArangoDB database instance.
        claim_id: Claim identifier.
    
    Returns:
        Source anchor dictionary with doc_id, page_number, bbox/span/snippet, or None if not found.
    """
    if not db.has_collection("extractions"):
        logger.warning("extractions collection not found in ArangoDB")
        return None
    
    try:
        # Query extractions collection for the claim
        query = """
        FOR e IN extractions
        FOR triple IN e.graph.triples
        FILTER triple.claim_id == @claim_id OR triple._key == @claim_id
        LIMIT 1
        RETURN {
            claim_id: triple.claim_id,
            source_anchor: triple.source_anchor,
            source_pointer: triple.source_pointer,
            file_hash: triple.file_hash
        }
        """
        
        cursor = db.aql.execute(query, bind_vars={"claim_id": claim_id})
        results = list(cursor)
        
        if not results:
            logger.debug(f"Claim {claim_id} not found in extractions")
            return None
        
        claim_data = results[0]
        
        # Prefer source_anchor, fallback to source_pointer
        source_anchor = claim_data.get("source_anchor")
        if source_anchor:
            return source_anchor
        
        # Convert source_pointer to source_anchor format
        source_pointer = claim_data.get("source_pointer", {})
        if not source_pointer:
            logger.warning(f"Claim {claim_id} has no source_anchor or source_pointer")
            return None
        
        # Convert source_pointer to source_anchor
        from ..schemas.claims import SourceAnchor
        
        anchor_data = {
            "doc_id": source_pointer.get("doc_hash") or claim_data.get("file_hash", ""),
            "page_number": source_pointer.get("page", 1),
        }
        
        # Add bbox if present (convert from [x1,y1,x2,y2] to {x,y,w,h})
        bbox = source_pointer.get("bbox")
        if bbox and isinstance(bbox, list) and len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            anchor_data["bbox"] = {
                "x": float(x1),
                "y": float(y1),
                "w": float(x2 - x1),
                "h": float(y2 - y1),
            }
        
        # Add snippet if present
        snippet = source_pointer.get("snippet")
        if snippet:
            anchor_data["snippet"] = snippet
        
        try:
            # Validate and return
            anchor = SourceAnchor(**anchor_data)
            return anchor.model_dump(exclude_none=True)
        except Exception as e:
            logger.warning(f"Failed to create SourceAnchor from source_pointer: {e}", exc_info=True)
            return None
        
    except Exception as e:
        logger.error(f"Failed to get claim anchor for {claim_id}: {e}", exc_info=True)
        return None

