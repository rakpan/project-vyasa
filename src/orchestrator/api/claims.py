"""
Claims API endpoints for retrieving claim details and anchors.
"""

from typing import Dict, Any, Optional
from flask import Blueprint, jsonify

from ...shared.logger import get_logger
from ..job_store import get_job_record
from ..utils.source_anchor import source_pointer_to_anchor

logger = get_logger("orchestrator", __name__)

# Flask Blueprint for claims routes
claims_bp = Blueprint("claims", __name__, url_prefix="/api/claims")


@claims_bp.route("/<claim_id>/anchor", methods=["GET"])
def get_claim_anchor(claim_id: str):
    """Get source anchor for a claim.
    
    Response:
        {
            "claim_id": str,
            "source_anchor": {
                "doc_id": str,
                "page_number": int,
                "span": {
                    "start": int,
                    "end": int
                } (optional),
                "bbox": {
                    "x": float,
                    "y": float,
                    "w": float,
                    "h": float
                } (optional),
                "snippet": str (optional)
            }
        }
    
    Errors:
        404: Claim not found
        503: Database unavailable
    """
    try:
        # Try to find claim in job results
        # For now, we'll search through recent jobs
        # In production, you might want to store claims in a dedicated collection
        
        from ..job_store import get_job_record
        from arango import ArangoClient
        from ...shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
        
        # Try to get from canonical_knowledge or candidate_knowledge
        try:
            client = ArangoClient(hosts=get_memory_url())
            db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
            
            # Search in canonical_knowledge
            if db.has_collection("canonical_knowledge"):
                coll = db.collection("canonical_knowledge")
                query = """
                FOR claim IN canonical_knowledge
                FILTER claim.claim_id == @claim_id OR claim._key == @claim_id
                LIMIT 1
                RETURN claim
                """
                cursor = db.aql.execute(query, bind_vars={"claim_id": claim_id})
                results = list(cursor)
                if results:
                    claim = results[0]
                    source_pointers = claim.get("source_pointers", [])
                    if source_pointers and isinstance(source_pointers, list):
                        # Use first source pointer
                        source_pointer = source_pointers[0] if isinstance(source_pointers[0], dict) else {}
                        anchor = source_pointer_to_anchor(source_pointer)
                        if anchor:
                            return jsonify({
                                "claim_id": claim_id,
                                "source_anchor": anchor,
                            }), 200
            
            # Search in candidate_knowledge
            if db.has_collection("candidate_knowledge"):
                coll = db.collection("candidate_knowledge")
                query = """
                FOR claim IN candidate_knowledge
                FILTER claim.claim_id == @claim_id OR claim._key == @claim_id
                LIMIT 1
                RETURN claim
                """
                cursor = db.aql.execute(query, bind_vars={"claim_id": claim_id})
                results = list(cursor)
                if results:
                    claim = results[0]
                    source_pointer = claim.get("source_pointer", {})
                    anchor = source_pointer_to_anchor(source_pointer)
                    if anchor:
                        return jsonify({
                            "claim_id": claim_id,
                            "source_anchor": anchor,
                        }), 200
        except Exception as e:
            logger.warning(f"Failed to query database for claim anchor: {e}", exc_info=True)
        
        # Fallback: search in job results
        # This is a simplified approach - in production, you might index claims differently
        return jsonify({"error": "Claim not found"}), 404
        
    except Exception as e:
        logger.error(f"Failed to get claim anchor: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

