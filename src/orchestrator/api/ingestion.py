"""
Ingestion API endpoints for Project Vyasa.

Provides endpoints for:
- Duplicate detection
- Ingestion status polling
- Retry operations
"""

import hashlib
import logging
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify

from ..ingestion_store import IngestionStore, IngestionStatus
from ..state import JobStatus
from ..job_manager import get_job
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# Flask Blueprint for ingestion routes
ingestion_bp = Blueprint("ingestion", __name__, url_prefix="/api/projects")


def _get_ingestion_store():
    """Get IngestionStore instance."""
    from ..server import get_project_service
    project_service = get_project_service()
    if project_service is None:
        return None
    return IngestionStore(project_service.db)


def _map_job_status_to_ingestion_status(job_status: str, current_step: Optional[str] = None) -> str:
    """Map backend JobStatus to IngestionStatus."""
    if job_status in (JobStatus.QUEUED.value, JobStatus.PENDING.value):
        return IngestionStatus.QUEUED
    if job_status in (JobStatus.RUNNING.value, JobStatus.PROCESSING.value):
        if current_step == "cartographer" or (current_step and "extract" in current_step.lower()):
            return IngestionStatus.EXTRACTING
        if current_step == "vision" or (current_step and "vision" in current_step.lower()):
            return IngestionStatus.MAPPING
        if current_step == "critic" or (current_step and "critic" in current_step.lower()):
            return IngestionStatus.VERIFYING
        return IngestionStatus.EXTRACTING  # Default for RUNNING
    if job_status in (JobStatus.SUCCEEDED.value, JobStatus.COMPLETED.value):
        return IngestionStatus.COMPLETED
    if job_status == JobStatus.FAILED.value:
        return IngestionStatus.FAILED
    return IngestionStatus.QUEUED


def _generate_first_glance_summary(job_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate first glance summary from job result.
    
    Args:
        job_result: Job result dictionary with extracted_json, etc.
    
    Returns:
        Dictionary with pages, tables_detected, figures_detected, text_density.
    """
    if not job_result:
        return {}
    
    summary: Dict[str, Any] = {}
    
    # Extract pages from raw_text or pdf_path
    raw_text = job_result.get("raw_text", "")
    if raw_text:
        # Estimate pages (rough: ~3000 chars per page)
        estimated_pages = max(1, len(raw_text) // 3000)
        summary["pages"] = estimated_pages
    
    # Extract tables and figures from extracted_json
    extracted_json = job_result.get("extracted_json", {})
    if isinstance(extracted_json, dict):
        triples = extracted_json.get("triples", [])
        if isinstance(triples, list):
            # Count tables and figures from triples
            tables_count = sum(1 for t in triples if "table" in str(t.get("object", "")).lower() or "table" in str(t.get("subject", "")).lower())
            figures_count = sum(1 for t in triples if "figure" in str(t.get("object", "")).lower() or "figure" in str(t.get("subject", "")).lower())
            
            summary["tables_detected"] = tables_count
            summary["figures_detected"] = figures_count
            
            # Calculate text density (triples per page)
            if summary.get("pages", 0) > 0:
                summary["text_density"] = round(len(triples) / summary["pages"], 2)
            else:
                summary["text_density"] = len(triples)
    
    return summary


def _calculate_confidence_badge(job_result: Optional[Dict[str, Any]]) -> Optional[str]:
    """Calculate confidence badge based on extraction quality.
    
    Args:
        job_result: Job result dictionary.
    
    Returns:
        "High", "Medium", or "Low" confidence badge.
    """
    if not job_result:
        return None
    
    extracted_json = job_result.get("extracted_json", {})
    if not isinstance(extracted_json, dict):
        return "Low"
    
    triples = extracted_json.get("triples", [])
    if not isinstance(triples, list):
        return "Low"
    
    total_triples = len(triples)
    if total_triples == 0:
        return "Low"
    
    # Count triples with evidence (source_pointer)
    triples_with_evidence = sum(
        1 for t in triples
        if isinstance(t, dict) and t.get("source_pointer") or t.get("evidence")
    )
    
    evidence_ratio = triples_with_evidence / total_triples if total_triples > 0 else 0.0
    
    if evidence_ratio >= 0.8 and total_triples >= 10:
        return "High"
    elif evidence_ratio >= 0.5 and total_triples >= 5:
        return "Medium"
    else:
        return "Low"


@ingestion_bp.route("/<project_id>/ingest/check-duplicate", methods=["POST"])
def check_duplicate(project_id: str):
    """Check if a file is a duplicate based on hash.
    
    Request body (JSON):
        {
            "sha256": str (SHA256 hex digest, required),
            "filename": str (optional, for logging),
            "size_bytes": int (optional)
        }
    
    Response:
        {
            "is_duplicate": bool,
            "matches": [
                {
                    "project_id": str,
                    "project_title": str,
                    "ingested_at": str (ISO timestamp)
                }
            ]
        }
    """
    try:
        data = request.json or {}
        # Accept both 'sha256' and 'file_hash' for backward compatibility
        file_hash = data.get("sha256", "").strip() or data.get("file_hash", "").strip()
        filename = data.get("filename", "")
        size_bytes = data.get("size_bytes")
        
        if not file_hash:
            return jsonify({"error": "sha256 is required"}), 400
        
        # Validate hash format (SHA256 = 64 hex chars)
        if len(file_hash) != 64 or not all(c in "0123456789abcdef" for c in file_hash.lower()):
            return jsonify({"error": "Invalid sha256 format (expected SHA256 hex digest, 64 characters)"}), 400
        
        ingestion_store = _get_ingestion_store()
        if ingestion_store is None:
            return jsonify({"error": "Database unavailable"}), 503
        
        duplicates = ingestion_store.find_duplicates(file_hash, exclude_project_id=project_id)
        
        # Format matches with ingested_at
        matches = []
        for dup in duplicates:
            # Get ingestion record to find ingested_at
            ingestion_records = ingestion_store.find_by_hash(file_hash, project_id=dup.get("project_id"))
            ingested_at = None
            if ingestion_records:
                # Get the most recent one
                latest = max(ingestion_records, key=lambda r: r.created_at or "")
                ingested_at = latest.created_at
            
            matches.append({
                "project_id": dup.get("project_id", ""),
                "project_title": dup.get("title", ""),
                "ingested_at": ingested_at or "",
            })
        
        return jsonify({
            "is_duplicate": len(matches) > 0,
            "matches": matches,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to check duplicate: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@ingestion_bp.route("/<project_id>/ingest/<ingestion_id>/status", methods=["GET"])
def get_ingestion_status(project_id: str, ingestion_id: str):
    """Get ingestion status with first glance summary.
    
    Response:
        {
            "ingestion_id": str,
            "status": "Queued" | "Extracting" | "Mapping" | "Verifying" | "Completed" | "Failed",
            "progress_pct": float (0-100),
            "error_message": str (if failed),
            "first_glance": {
                "pages": int,
                "tables_detected": int,
                "figures_detected": int,
                "text_density": float
            } (if available),
            "confidence_badge": "High" | "Medium" | "Low" (if available)
        }
    """
    try:
        ingestion_store = _get_ingestion_store()
        if ingestion_store is None:
            return jsonify({"error": "Database unavailable"}), 503
        
        record = ingestion_store.get_ingestion(ingestion_id)
        if not record:
            return jsonify({"error": "Ingestion not found"}), 404
        
        if record.project_id != project_id:
            return jsonify({"error": "Ingestion does not belong to this project"}), 403
        
        # Sync status from job if available
        status = record.status
        progress_pct = record.progress_pct
        error_message = record.error_message
        first_glance = record.first_glance
        confidence_badge = record.confidence_badge
        
        if record.job_id:
            job = get_job(record.job_id)
            if job:
                # Update status from job
                status = _map_job_status_to_ingestion_status(
                    job.get("status", JobStatus.QUEUED.value) if isinstance(job.get("status"), JobStatus) else str(job.get("status", "")),
                    job.get("current_step")
                )
                progress_pct = (job.get("progress", 0.0) or 0.0) * 100
                error_message = job.get("error")
                
                # Generate first glance if job completed and not already set
                if status == IngestionStatus.COMPLETED and not first_glance:
                    job_result = job.get("result")
                    first_glance = _generate_first_glance_summary(job_result)
                    confidence_badge = _calculate_confidence_badge(job_result)
                    
                    # Update record with first glance
                    ingestion_store.update_ingestion(
                        ingestion_id,
                        status=status,
                        progress_pct=progress_pct,
                        error_message=error_message,
                        first_glance=first_glance,
                        confidence_badge=confidence_badge,
                    )
                elif status != record.status or progress_pct != record.progress_pct:
                    # Update status/progress if changed
                    ingestion_store.update_ingestion(
                        ingestion_id,
                        status=status,
                        progress_pct=progress_pct,
                        error_message=error_message,
                    )
        
        response: Dict[str, Any] = {
            "ingestion_id": ingestion_id,
            "state": status,  # Use 'state' as per contract
            "progress_pct": progress_pct if progress_pct is not None else None,
        }
        
        # Include job_id if available
        if record.job_id:
            response["job_id"] = record.job_id
        
        # Only include error_message if Failed
        if status == IngestionStatus.FAILED and error_message:
            response["error_message"] = error_message
        
        # Only include first_glance when available
        if first_glance:
            response["first_glance"] = first_glance
        
        # Only include confidence after extraction (when badge is available)
        if confidence_badge:
            response["confidence"] = confidence_badge
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Failed to get ingestion status: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@ingestion_bp.route("/<project_id>/ingest/<ingestion_id>/retry", methods=["POST"])
def retry_ingestion(project_id: str, ingestion_id: str):
    """Retry a failed ingestion.
    
    Creates a new job for the existing ingestion record.
    Requires the file to be re-uploaded via /workflow/submit with the same ingestion_id.
    
    Response:
        {
            "ingestion_id": str,
            "state": "Queued",
            "job_id": str (new job ID, or same if requeued)
        }
    """
    try:
        ingestion_store = _get_ingestion_store()
        if ingestion_store is None:
            return jsonify({"error": "Database unavailable"}), 503
        
        record = ingestion_store.get_ingestion(ingestion_id)
        if not record:
            return jsonify({"error": "Ingestion not found"}), 404
        
        if record.project_id != project_id:
            return jsonify({"error": "Ingestion does not belong to this project"}), 403
        
        # Allow retry for Failed or Completed (for reprocessing)
        if record.status not in (IngestionStatus.FAILED, IngestionStatus.COMPLETED):
            return jsonify({"error": "Can only retry failed or completed ingestions"}), 400
        
        # Reset status to Queued and clear error
        ingestion_store.update_ingestion(
            ingestion_id,
            status=IngestionStatus.QUEUED,
            error_message=None,
            progress_pct=0.0,
            job_id=None,  # Clear old job_id, will be set when new job is created
        )
        
        # Note: New job_id will be set when client calls /workflow/submit with ingestion_id
        # For now, return the ingestion_id with Queued state
        return jsonify({
            "ingestion_id": ingestion_id,
            "state": IngestionStatus.QUEUED,
            "job_id": None,  # Will be set after re-upload
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to retry ingestion: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@ingestion_bp.route("/<project_id>/ingest/<ingestion_id>", methods=["DELETE"])
def delete_ingestion(project_id: str, ingestion_id: str):
    """Remove an ingestion record (soft delete).
    
    If a job is running, marks it as cancelled best-effort.
    
    Response:
        {
            "ingestion_id": str,
            "deleted": bool
        }
    """
    try:
        ingestion_store = _get_ingestion_store()
        if ingestion_store is None:
            return jsonify({"error": "Database unavailable"}), 503
        
        record = ingestion_store.get_ingestion(ingestion_id)
        if not record:
            return jsonify({"error": "Ingestion not found"}), 404
        
        if record.project_id != project_id:
            return jsonify({"error": "Ingestion does not belong to this project"}), 403
        
        # If job is running, try to cancel it (best-effort)
        if record.job_id:
            try:
                job = get_job(record.job_id)
                if job and job.get("status") in ("RUNNING", "PROCESSING", "QUEUED", "PENDING"):
                    # Mark job as cancelled (if job_store supports it)
                    from ..job_store import update_job_record
                    update_job_record(record.job_id, {"status": "CANCELLED"})
                    logger.info(f"Marked job {record.job_id} as cancelled for ingestion {ingestion_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel job {record.job_id}: {e}", exc_info=True)
                # Continue with deletion even if cancel fails
        
        # Soft delete: mark as deleted (or hard delete if preferred)
        # For now, we'll hard delete the record
        try:
            collection = ingestion_store.db.collection("ingestions")
            collection.delete(ingestion_id)
            logger.info(f"Deleted ingestion {ingestion_id} for project {project_id}")
        except Exception as e:
            logger.error(f"Failed to delete ingestion {ingestion_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to delete ingestion"}), 500
        
        return jsonify({
            "ingestion_id": ingestion_id,
            "deleted": True,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to delete ingestion: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

