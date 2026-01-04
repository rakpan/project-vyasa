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
    
    Fetches claim from ArangoDB extractions collection and returns source_anchor verbatim.
    
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
        from arango import ArangoClient
        from ...shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
        from ..storage.arango import get_claim_anchor as get_anchor_from_db
        
        try:
            client = ArangoClient(hosts=get_memory_url())
            db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
            
            # Get anchor from ArangoDB
            source_anchor = get_anchor_from_db(db, claim_id)
            
            if source_anchor:
                return jsonify({
                    "claim_id": claim_id,
                    "source_anchor": source_anchor,
                }), 200
            else:
                return jsonify({"error": "Claim not found"}), 404
                
        except Exception as e:
            logger.warning(f"Failed to query database for claim anchor: {e}", exc_info=True)
            return jsonify({"error": "Database unavailable"}), 503
        
    except Exception as e:
        logger.error(f"Failed to get claim anchor: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

