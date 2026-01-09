"""
Manuscript Blueprint API for Project Vyasa.

Handles CRUD operations for Manuscript Blueprints and section synthesis runs.
The Blueprint Engine governs manuscript synthesis by defining sections,
linked RQs, evidence clusters, depth intent, and visual anchors.
"""

import uuid
from typing import List, Optional, Dict, Any
from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from ..schemas.blueprint import (
    ManuscriptBlueprint,
    BlueprintSection,
    JournalSlot,
    DepthIntent,
)
from ..services.blueprint_service import BlueprintService
from ..section_synthesis import SectionSynthesisError
from ...shared.config import get_memory_url, get_arango_password, ARANGODB_DB, ARANGODB_USER
from ...shared.logger import get_logger
from arango import ArangoClient
from arango.database import StandardDatabase
from arango.exceptions import ArangoError

logger = get_logger("orchestrator", __name__)

# Flask Blueprint for blueprint routes
blueprint_bp = Blueprint("blueprint", __name__, url_prefix="/api")


def _get_db() -> Optional[StandardDatabase]:
    """Get ArangoDB database connection.
    
    Returns:
        StandardDatabase instance or None if connection fails.
    """
    try:
        client = ArangoClient(hosts=get_memory_url())
        db = client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
        return db
    except Exception as e:
        logger.error(f"Failed to connect to ArangoDB: {e}", exc_info=True)
        return None


def _get_blueprint_service() -> Optional[BlueprintService]:
    """Get BlueprintService instance.
    
    Returns:
        BlueprintService instance or None if DB unavailable.
    """
    db = _get_db()
    if not db:
        return None
    return BlueprintService(db)


@blueprint_bp.route("/projects/<project_id>/blueprint", methods=["GET"])
def get_blueprint(project_id: str):
    """Get Manuscript Blueprint for a project.
    
    Query parameters:
        version: Optional version number (default: latest)
    
    Returns:
        ManuscriptBlueprint object or 404 if not found.
    """
    service = _get_blueprint_service()
    if not service:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        version_str = request.args.get("version")
        version = int(version_str) if version_str else None
        
        blueprint = service.get_blueprint(project_id, version=version)
        if not blueprint:
            return jsonify({"error": "Blueprint not found"}), 404
        
        return jsonify(blueprint.model_dump()), 200
    
    except ValueError:
        return jsonify({"error": "Invalid version"}), 400
    except Exception as e:
        logger.error(f"Failed to get blueprint: {e}", exc_info=True)
        return jsonify({"error": "Failed to get blueprint"}), 500


@blueprint_bp.route("/projects/<project_id>/blueprint", methods=["POST"])
def save_blueprint(project_id: str):
    """Save a Manuscript Blueprint.
    
    Request body (JSON):
        {
            "sections": List[BlueprintSection] (required, at least one section),
            "target_journal": str (optional),
        }
    
    BlueprintSection structure:
        {
            "section_id": str (optional, will be generated),
            "heading": str (required),
            "journal_slot": str (required, one of: introduction, methods, results, discussion, conclusion, abstract, background, related_work),
            "linked_rqs": List[str] (optional, default: []),
            "evidence_cluster_ids": List[str] (optional, default: []),
            "depth_intent": str (optional, default: "proof", one of: hook, proof, so_what),
            "visual_anchors": List[VisualAnchor] (optional, default: []),
            "conclusion_rules": str (optional),
        }
    
    Returns:
        Saved ManuscriptBlueprint object with generated blueprint_id and version.
    """
    service = _get_blueprint_service()
    if not service:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        payload = request.json or {}
        
        # Validate sections
        sections_data = payload.get("sections", [])
        if not sections_data or not isinstance(sections_data, list):
            return jsonify({"error": "Blueprint must have at least one section"}), 400
        
        # Validate sections minimal fields
        sections = []
        for section_data in sections_data:
            # Generate section_id if not provided
            if "section_id" not in section_data:
                section_data["section_id"] = str(uuid.uuid4())
            
            # Validate required fields
            if not section_data.get("heading") or not section_data["heading"].strip():
                return jsonify({"error": "Section heading must be non-empty"}), 400
            
            if not section_data.get("journal_slot"):
                return jsonify({"error": "Section journal_slot is required"}), 400
            
            # Validate journal_slot enum
            try:
                JournalSlot(section_data["journal_slot"])
            except ValueError:
                return jsonify({
                    "error": f"Invalid journal_slot: {section_data['journal_slot']}. Must be one of: {[slot.value for slot in JournalSlot]}"
                }), 400
            
            # Validate depth_intent enum if provided
            if "depth_intent" in section_data:
                try:
                    DepthIntent(section_data["depth_intent"])
                except ValueError:
                    return jsonify({
                        "error": f"Invalid depth_intent: {section_data['depth_intent']}. Must be one of: {[intent.value for intent in DepthIntent]}"
                    }), 400
            
            sections.append(BlueprintSection(**section_data))
        
        # Create blueprint
        blueprint = ManuscriptBlueprint.create(
            project_id=project_id,
            sections=sections,
            target_journal=payload.get("target_journal"),
        )
        
        # Save blueprint
        blueprint = service.save_blueprint(blueprint)
        
        return jsonify(blueprint.model_dump()), 201
    
    except ValidationError as e:
        return jsonify({"error": "Validation failed", "details": e.errors()}), 400
    except ValueError:
        return jsonify({"error": "Invalid blueprint payload"}), 400
    except Exception as e:
        logger.error(f"Failed to save blueprint: {e}", exc_info=True)
        return jsonify({"error": "Failed to save blueprint"}), 500


@blueprint_bp.route("/projects/<project_id>/sections/<section_id>/run", methods=["POST"])
def run_section(project_id: str, section_id: str):
    """Run section synthesis loop for a blueprint section.
    
    Request body (JSON):
        {
            "ingestion_id": str (required for retrieval),
            "blueprint_version": int (optional, default: latest),
        }
    
    Returns:
        Job ID for async section synthesis (status can be checked via /status endpoint).
    
    Note: This endpoint triggers async section synthesis. The actual synthesis loop
    will be implemented in a separate blueprint_synthesis_node. For now, this
    creates a placeholder job and returns immediately.
    """
    from ..job_store import create_job_record, update_job_record, set_job_result_record
    from ..state import JobStatus
    
    try:
        payload = request.json or {}
        ingestion_id = payload.get("ingestion_id")
        blueprint_version = payload.get("blueprint_version")
        
        # Validate ingestion_id is required
        if not ingestion_id or not ingestion_id.strip():
            return jsonify({"error": "ingestion_id is required for retrieval"}), 400
        
        # Get blueprint
        service = _get_blueprint_service()
        if not service:
            return jsonify({"error": "Database unavailable"}), 503
        
        blueprint = service.get_blueprint(project_id, version=blueprint_version)
        if not blueprint:
            return jsonify({"error": "Blueprint not found"}), 404
        
        # Find section
        section = next((s for s in blueprint.sections if s.section_id == section_id), None)
        if not section:
            return jsonify({"error": f"Section {section_id} not found in blueprint"}), 404
        
        # Check for duplicate/active runs (prevent duplicate runs)
        idempotency_key = f"section_run_{project_id}_{section_id}_{blueprint.version}"
        from ..job_store import get_job_by_idempotency_key
        existing_job = get_job_by_idempotency_key(idempotency_key)
        
        if existing_job:
            existing_status = existing_job.get("status")
            # If job is still running or queued, return existing job info
            if existing_status in ("RUNNING", "QUEUED", "PROCESSING"):
                return jsonify({
                    "error": "Section run already in progress",
                    "job_id": existing_job.get("job_id"),
                    "status": existing_status,
                    "message": "A section run for this section is already in progress. Please wait for it to complete.",
                }), 409  # Conflict status code
        
        # Create job record for section synthesis
        initial_state = {
            "project_id": project_id,
            "section_id": section_id,
            "ingestion_id": ingestion_id,
            "blueprint_id": blueprint.blueprint_id,
            "blueprint_version": blueprint.version,
        }
        
        job_id = create_job_record(
            initial_state=initial_state,
            idempotency_key=idempotency_key,
        )
        
        logger.info(
            f"Created section synthesis job",
            extra={
                "payload": {
                    "job_id": job_id,
                    "project_id": project_id,
                    "section_id": section_id,
                    "blueprint_version": blueprint.version,
                }
            }
        )
        
        # Trigger section synthesis loop (synchronous for now)
        # TODO: Make async in future
        try:
            from ..section_synthesis.section_orchestrator import run_section_synthesis
            
            db = _get_db()
            if not db:
                return jsonify({"error": "Database unavailable"}), 503
            
            # Run section synthesis
            results = run_section_synthesis(
                project_id=project_id,
                section_id=section_id,
                ingestion_id=ingestion_id,
                blueprint_version=blueprint_version,
                db=db,
                job_id=job_id,
            )
            
            logger.info(
                f"Section synthesis completed",
                extra={
                    "payload": {
                        "job_id": job_id,
                        "project_id": project_id,
                        "section_id": section_id,
                        "bundle_id": results.get("bundle_id"),
                        "block_id": results.get("block_id"),
                        "promotions_applied": results.get("promotions_applied", 0),
                    }
                }
            )
            
            # Update job status to SUCCEEDED with result payload
            result_payload = {
                "bundle_id": results.get("bundle_id"),
                "block_id": results.get("block_id"),
                "block_ids": results.get("block_ids", []),
                "promotions_applied": results.get("promotions_applied", 0),
                "critique_summary": results.get("critique", {}).get("overreach_flags", []) if results.get("critique") else None,
            }
            
            try:
                set_job_result_record(job_id, result_payload)
            except Exception as e:
                logger.warning(
                    f"Failed to update job result record: {e}",
                    extra={"payload": {"job_id": job_id}},
                    exc_info=True
                )
                # Fallback to update_job_record
                update_job_record(job_id, {
                    "status": JobStatus.SUCCEEDED.value,
                    "result": result_payload,
                    "progress": 1.0,
                    "message": "Section synthesis completed",
                })
            
            return jsonify({
                "job_id": job_id,
                "status": JobStatus.SUCCEEDED.value,
                "results": {
                    **result_payload,
                    "section_text_preview": results.get("section_text", "")[:200] + "..." if results.get("section_text") else None,
                },
            }), 200
            
        except SectionSynthesisError as e:
            logger.error(
                f"Section synthesis failed: {e}",
                extra={
                    "payload": {
                        "job_id": job_id,
                        "project_id": project_id,
                        "section_id": section_id,
                    }
                },
                exc_info=True
            )
            
            # Update job status to FAILED
            try:
                update_job_record(job_id, {
                    "status": JobStatus.FAILED.value,
                    "error": "Section synthesis failed",
                    "progress": 0.0,
                    "message": "Section synthesis failed",
                })
            except Exception as e:
                logger.warning(
                    f"Failed to update job status to FAILED: {e}",
                    extra={"payload": {"job_id": job_id}},
                    exc_info=True
                )
            
            return jsonify({
                "job_id": job_id,
                "status": JobStatus.FAILED.value,
                "error": "Section synthesis failed",
            }), 500
        except Exception as e:
            # Unexpected error (not SectionSynthesisError)
            logger.error(
                f"Unexpected error during section synthesis: {e}",
                extra={
                    "payload": {
                        "job_id": job_id,
                        "project_id": project_id,
                        "section_id": section_id,
                    }
                },
                exc_info=True
            )
            
            # Update job status to FAILED
            try:
                update_job_record(job_id, {
                    "status": JobStatus.FAILED.value,
                    "error": "Unexpected error during section synthesis",
                    "progress": 0.0,
                    "message": "Section synthesis failed with unexpected error",
                })
            except Exception as update_error:
                logger.warning(
                    f"Failed to update job status to FAILED: {update_error}",
                    extra={"payload": {"job_id": job_id}},
                    exc_info=True
                )
            
            return jsonify({
                "job_id": job_id,
                "status": JobStatus.FAILED.value,
                "error": "Unexpected error during section synthesis",
            }), 500
    
    except Exception as e:
        logger.error(f"Failed to create section synthesis job: {e}", exc_info=True)
        return jsonify({"error": "Failed to create section synthesis job"}), 500


@blueprint_bp.route("/projects/<project_id>/sections/<section_id>/status", methods=["GET"])
def get_section_status(project_id: str, section_id: str):
    """Get section synthesis status.
    
    Query parameters:
        job_id: Optional job ID to check status for
    
    Returns:
        Section synthesis status with job_id, status, progress, and result if completed.
    """
    from ..job_store import get_job_record
    
    try:
        job_id = request.args.get("job_id")
        if not job_id:
            return jsonify({"error": "job_id query parameter is required"}), 400
        
        job_record = get_job_record(job_id)
        if not job_record:
            return jsonify({"error": "Job not found"}), 404
        
        # Verify job belongs to this section
        initial_state = job_record.get("initial_state", {})
        if initial_state.get("project_id") != project_id or initial_state.get("section_id") != section_id:
            return jsonify({"error": "Job does not belong to this section"}), 403
        
        status = job_record.get("status")
        progress = job_record.get("progress", 0.0)
        current_step = job_record.get("current_step")
        tier = job_record.get("tier")  # Tier from job record (set by update_progress)
        
        # Map current_step to stage
        stage_map = {
            "query_building": "query_building",
            "retrieval": "retrieval",
            "rerank": "rerank",
            "packet_a": "evidence_pack",  # Map to evidence_pack for consistency
            "packet_b": "packet_b",
            "cartographer_pass2": "cartographer_pass2",
            "critique": "critic_verify",  # Map to critic_verify for consistency
            "synthesis": "synthesis",
            "persist": "persist",
            "complete": "complete",
        }
        # Return None for unmapped stages (not "unknown")
        stage = stage_map.get(current_step) if current_step else None
        
        # If tier not in job record, infer from stage (fallback)
        if not tier and current_step:
            from ..state import ExecutionTier
            from ..section_synthesis.section_orchestrator import STAGE_TIER_MAP
            tier_obj = STAGE_TIER_MAP.get(current_step)
            tier = tier_obj.value if tier_obj else None
        
        result = {
            "job_id": job_id,
            "status": status,
            "stage": stage,
            "tier": tier,  # Tier A or Tier B (or None for terminal states)
            "current_step": current_step,  # Include raw current_step for debugging
            "progress_percent": round(progress * 100, 1) if progress is not None else None,
            "progress": progress,
            "message": job_record.get("message"),
            "error": job_record.get("error"),
            "result": job_record.get("result"),
            "created_at": job_record.get("created_at"),
            "updated_at": job_record.get("updated_at"),
        }
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Failed to get section status: {e}", exc_info=True)
        return jsonify({"error": "Failed to get section status"}), 500


@blueprint_bp.route("/projects/<project_id>/manuscript/blocks", methods=["GET"])
def list_manuscript_blocks(project_id: str):
    """List manuscript blocks for a project (compiled manuscript).
    
    Query parameters:
        section_id: Optional section identifier filter
        order_by: Optional sort field (default: "order_index")
    
    Returns:
        JSON array of ManuscriptBlock objects (latest versions only).
    """
    from ...manuscript.service import ManuscriptService
    
    try:
        db = _get_db()
        if not db:
            return jsonify({"error": "Database unavailable"}), 503
        
        service = ManuscriptService(db)
        
        section_id = request.args.get("section_id")
        order_by = request.args.get("order_by", "order_index")
        
        # List blocks
        blocks = service.list_blocks(project_id, order_by=order_by)
        
        # Filter by section_id if provided
        if section_id:
            blocks = [b for b in blocks if getattr(b, "section_id", None) == section_id]
        
        return jsonify([block.model_dump(by_alias=True) for block in blocks]), 200
    
    except Exception as e:
        logger.error(f"Failed to list manuscript blocks: {e}", exc_info=True)
        return jsonify({"error": "Failed to list manuscript blocks"}), 500
