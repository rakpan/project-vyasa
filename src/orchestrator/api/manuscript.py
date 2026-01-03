"""
Manuscript API endpoints for block management and forking.
"""

import json
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify

from arango import ArangoClient
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

from ...shared.config import (
    get_memory_url,
    ARANGODB_DB,
    ARANGODB_USER,
    get_arango_password,
    get_brain_url,
)
from ...shared.model_registry import get_model_config
from ...shared.logger import get_logger
from ..nodes import route_to_expert, call_expert_with_fallback, ExpertType
from ..telemetry import TelemetryEmitter

logger = get_logger("orchestrator", __name__)
telemetry_emitter = TelemetryEmitter()

# Flask Blueprint for manuscript routes
manuscript_bp = Blueprint("manuscript", __name__, url_prefix="/api/projects/<project_id>/blocks")


def _get_db() -> Optional[StandardDatabase]:
    """Get ArangoDB database connection."""
    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        return db
    except Exception as e:
        logger.error(f"Failed to connect to ArangoDB: {e}", exc_info=True)
        return None


def _get_block_by_id(db: StandardDatabase, project_id: str, block_id: str) -> Optional[Dict[str, Any]]:
    """Get a manuscript block by project_id and block_id (latest version)."""
    try:
        query = """
        FOR b IN manuscript_blocks
        FILTER b.project_id == @project_id AND b.block_id == @block_id
        SORT b.version DESC
        LIMIT 1
        RETURN b
        """
        cursor = db.aql.execute(query, bind_vars={"project_id": project_id, "block_id": block_id})
        blocks = list(cursor)
        if blocks:
            block = blocks[0]
            # Remove ArangoDB internal fields
            block.pop("_id", None)
            block.pop("_key", None)
            block.pop("_rev", None)
            return block
        return None
    except ArangoError as e:
        logger.error(f"Failed to get block: {e}", exc_info=True)
        return None


def _get_triples_by_claim_ids(db: StandardDatabase, project_id: str, claim_ids: List[str], job_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get triples/claims by claim IDs from workflow results."""
    if not claim_ids:
        return []
    
    triples = []
    
    # Try to get from job results if job_id is provided
    if job_id:
        try:
            from ..job_store import get_job_record
            job_record = get_job_record(job_id)
            if job_record:
                result = job_record.get("result", {})
                extracted_json = result.get("extracted_json", {})
                all_triples = extracted_json.get("triples", [])
                
                # Filter by claim_ids
                for triple in all_triples:
                    if not isinstance(triple, dict):
                        continue
                    triple_claim_id = triple.get("claim_id")
                    if triple_claim_id and triple_claim_id in claim_ids:
                        triples.append(triple)
        except Exception as e:
            logger.warning(f"Failed to get triples from job: {e}")
    
    # Fallback: query from canonical_knowledge or graph_triples if needed
    # For now, return what we found from job results
    return triples


@manuscript_bp.route("/<block_id>/fork", methods=["POST"])
def fork_block(project_id: str, block_id: str):
    """Fork a manuscript block with a different rigor level.
    
    Request body:
        {
            "rigor_level": "exploratory" | "conservative"
        }
    
    Response:
        {
            "forked_block": {
                "block_id": str,
                "section_title": str,
                "content": str,
                "claim_ids": List[str],
                "citation_keys": List[str],
                "rigor_level": str
            }
        }
    
    Errors:
        404: Block not found
        400: Invalid rigor level
        503: Database unavailable
        500: Fork generation failed
    """
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        payload = request.json or {}
        rigor_level = (payload.get("rigor_level") or "").strip().lower()
        
        if rigor_level not in ("exploratory", "conservative"):
            return jsonify({"error": "rigor_level must be 'exploratory' or 'conservative'"}), 400
        
        # Get original block
        original_block = _get_block_by_id(db, project_id, block_id)
        if not original_block:
            return jsonify({"error": "Block not found"}), 404
        
        # Get claim_ids and fetch triples
        claim_ids = original_block.get("claim_ids", [])
        
        # Try to get job_id from project context or use a default approach
        # For now, we'll need to get triples from the most recent job
        # This is a simplified approach - in production, you might want to store job_id with blocks
        job_id = payload.get("job_id")  # Optional: allow passing job_id
        
        triples = _get_triples_by_claim_ids(db, project_id, claim_ids, job_id)
        
        if not triples:
            return jsonify({"error": "No triples found for block claims"}), 400
        
        # Generate forked block content using Synthesizer
        section_title = original_block.get("section_title", "Section")
        citation_keys = original_block.get("citation_keys", [])
        
        # Build synthesis prompt
        system_prompt = f"""You are the Synthesizer. Generate a manuscript section from knowledge graph triples.

Rigor Level: {rigor_level.upper()}
- {"Conservative: Use precise, verified language. Avoid speculation. Cite all claims." if rigor_level == "conservative" else "Exploratory: Allow broader interpretations and connections. Can suggest hypotheses."}

Section Title: {section_title}

Generate a well-structured markdown section that:
1. Synthesizes the provided triples into coherent narrative
2. Maintains traceability to claim IDs
3. Includes appropriate citations
4. Follows the rigor level constraints

Output ONLY the markdown content, no metadata."""
        
        # Format triples as JSON for context
        triples_json = json.dumps(triples, indent=2)
        user_prompt = f"Triples:\n{triples_json}\n\nCitations: {', '.join(citation_keys) if citation_keys else 'None'}"
        
        # Call Synthesizer expert
        expert_url, expert_name, expert_model = route_to_expert(
            "synthesizer_fork", ExpertType.SYNTHESIS
        )
        fallback_url = get_brain_url() if expert_name == "Worker" else None
        fallback_model = get_model_config("brain").model_id if fallback_url else None
        
        state = {"project_id": project_id, "job_id": job_id or "fork"}
        prompt = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        data, meta = call_expert_with_fallback(
            expert_url=expert_url,
            expert_name=expert_name,
            model_id=expert_model,
            prompt=prompt,
            request_params={
                "temperature": 0.7 if rigor_level == "exploratory" else 0.5,
                "top_p": 0.95,
                "max_tokens": 2048,
            },
            fallback_url=fallback_url,
            fallback_model_id=fallback_model,
            node_name="synthesizer_fork",
            state=state,
        )
        
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Build forked block response
        forked_block = {
            "block_id": block_id,
            "section_title": section_title,
            "content": content,
            "claim_ids": claim_ids,
            "citation_keys": citation_keys,
            "rigor_level": rigor_level,
            "original_version": original_block.get("version", 1),
        }
        
        # Emit telemetry
        telemetry_emitter.emit_event(
            "block_forked",
            {
                "project_id": project_id,
                "block_id": block_id,
                "rigor_level": rigor_level,
                "claim_count": len(claim_ids),
            },
        )
        
        return jsonify({"forked_block": forked_block}), 200
        
    except Exception as e:
        logger.error(f"Failed to fork block: {e}", exc_info=True)
        return jsonify({"error": "Failed to fork block"}), 500


@manuscript_bp.route("/<block_id>/accept-fork", methods=["POST"])
def accept_fork(project_id: str, block_id: str):
    """Accept a forked block as a new version.
    
    Request body:
        {
            "content": str,
            "section_title": str (optional),
            "rigor_level": str
        }
    
    Response:
        {
            "block": ManuscriptBlock (new version),
            "version": int
        }
    
    Errors:
        400: Missing required fields
        503: Database unavailable
        500: Failed to save block
    """
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        payload = request.json or {}
        content = payload.get("content", "").strip()
        
        if not content:
            return jsonify({"error": "content is required"}), 400
        
        # Get original block to preserve metadata
        original_block = _get_block_by_id(db, project_id, block_id)
        if not original_block:
            return jsonify({"error": "Original block not found"}), 404
        
        # Import ManuscriptService
        from ...manuscript.service import ManuscriptService
        from ...shared.schema import ManuscriptBlock
        
        manuscript_service = ManuscriptService(db)
        
        # Create new block version
        new_block = ManuscriptBlock(
            block_id=block_id,
            section_title=payload.get("section_title") or original_block.get("section_title", "Section"),
            content=content,
            claim_ids=original_block.get("claim_ids", []),
            citation_keys=original_block.get("citation_keys", []),
            order_index=original_block.get("order_index", 0),
            project_id=project_id,
        )
        
        # Save as new version
        saved_block = manuscript_service.save_block(new_block, project_id, validate_citations=True)
        
        # Emit telemetry
        telemetry_emitter.emit_event(
            "block_fork_accepted",
            {
                "project_id": project_id,
                "block_id": block_id,
                "version": saved_block.version,
                "rigor_level": payload.get("rigor_level"),
            },
        )
        
        return jsonify({
            "block": saved_block.model_dump(by_alias=True),
            "version": saved_block.version,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to accept fork: {e}", exc_info=True)
        return jsonify({"error": "Failed to accept fork"}), 500

