"""
Lightweight ingestion API for Project Vyasa.

Exposes a PDF-to-Markdown conversion endpoint that uses pymupdf4llm and the
shared logger, enabling the Console to send raw PDFs without losing structure.
"""

import threading
from pathlib import Path
import tempfile
from flask import Flask, request, jsonify

from .pdf_processor import process_pdf
from .workflow import build_workflow
from .state import PaperState, JobStatus
from .job_manager import (
    create_job,
    get_job,
    update_job_status,
    set_job_result,
    acquire_job_slot,
    release_job_slot,
)
from .normalize import normalize_extracted_json
from ..shared.logger import get_logger

logger = get_logger("orchestrator", __name__)
app = Flask(__name__)
workflow_app = build_workflow()


@app.route("/ingest/pdf", methods=["POST"])
def ingest_pdf():
    """Accept a PDF upload, convert to Markdown, return the text and image info."""
    if "file" not in request.files:
        return jsonify({"error": "Missing file field"}), 400

    uploaded = request.files["file"]
    if uploaded.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if not uploaded.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Invalid file format. Only PDF allowed."}), 400

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / uploaded.filename
            uploaded.save(pdf_path)

            images_dir = Path(tmpdir) / "images"
            markdown, images_output_dir, image_paths = process_pdf(str(pdf_path), output_image_dir=str(images_dir))

            return jsonify(
                {
                    "markdown": markdown,
                    "images": image_paths,
                    "filename": uploaded.filename,
                    "image_dir": str(images_output_dir) if images_output_dir else None,
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "PDF ingestion failed",
            extra={"payload": {"filename": uploaded.filename}},
            exc_info=True,
        )
        return jsonify({"error": str(exc)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Docker healthcheck."""
    return jsonify({"status": "healthy", "service": "orchestrator"}), 200


def _run_workflow_async(job_id: str, initial_state: PaperState) -> None:
    """Run workflow in background thread.
    
    Args:
        job_id: Job identifier.
        initial_state: Initial workflow state.
    """
    try:
        # Acquire job slot (concurrency control)
        if not acquire_job_slot():
            update_job_status(job_id, JobStatus.FAILED, error="Job queue full (max 2 concurrent jobs)")
            return
        
        try:
            update_job_status(job_id, JobStatus.RUNNING, current_step="Starting", progress=0.0, message="Starting")
            
            # Run the full workflow graph (handles retry logic internally)
            # The workflow will execute: cartographer -> critic -> (retry if needed) -> saver
            result = workflow_app.invoke(initial_state)
            
            # Update progress during execution (simplified - in production, use workflow callbacks)
            update_job_status(job_id, JobStatus.RUNNING, current_step="Cartographer", progress=0.2)
            update_job_status(job_id, JobStatus.RUNNING, current_step="Critic", progress=0.6)
            update_job_status(job_id, JobStatus.RUNNING, current_step="Saver", progress=0.9)
            
            # Ensure extracted_json has triples (normalize if needed)
            extracted_json = result.get("extracted_json", {})
            if not isinstance(extracted_json, dict) or "triples" not in extracted_json:
                result["extracted_json"] = normalize_extracted_json(extracted_json)
            
            # Set result
            set_job_result(job_id, result)
            
        finally:
            # Always release the slot
            release_job_slot()
            
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Workflow execution failed for job {job_id}", exc_info=True)
        update_job_status(job_id, JobStatus.FAILED, error=str(exc), message="Failed")


@app.route("/workflow/submit", methods=["POST"])
def submit_workflow():
    """Submit a workflow job for asynchronous processing.
    
    Accepts raw text or PDF file and returns a job_id for status polling.
    
    Request body (JSON):
        {
            "raw_text": str (required if no file),
            "pdf_path": str (optional),
            "extracted_json": dict (optional, for manual override),
            "critiques": list (optional),
            "revision_count": int (optional)
        }
    
    Request body (multipart/form-data):
        file: PDF file (optional, if provided, will extract text first)
    
    Response:
        {
            "job_id": "uuid-string",
            "status": "PENDING"
        }
    """
    try:
        # Handle file upload
        raw_text = ""
        pdf_path = ""
        payload_images: list[str] = []
        
        if request.content_type and "multipart/form-data" in request.content_type:
            if "file" in request.files:
                uploaded = request.files["file"]
                if uploaded.filename:
                    # Save to temp and extract text
                    tmpdir = tempfile.mkdtemp(prefix="vyasa_pdf_")
                    pdf_path = str(Path(tmpdir) / uploaded.filename)
                    uploaded.save(pdf_path)
                    
                    # Extract markdown from PDF (keep images around)
                    markdown, images_dir, image_paths = process_pdf(pdf_path)
                    raw_text = markdown
                    pdf_path = uploaded.filename  # Use original filename
                    payload_images = image_paths
        else:
            # JSON request
            payload = request.json or {}
            raw_text = payload.get("raw_text") or ""
            pdf_path = payload.get("pdf_path", "")
        
        if not raw_text:
            return jsonify({"error": "raw_text is required (or provide a PDF file)"}), 400
        
        # Create job
        job_id = create_job(initial_state, idempotency_key=payload.get("idempotency_key") if 'payload' in locals() else None)
        
        # Prepare initial state
        payload = request.json or {} if not (request.content_type and "multipart/form-data" in request.content_type) else {}
        initial_state: PaperState = {
            "raw_text": raw_text,
            "pdf_path": pdf_path or payload.get("pdf_path", ""),
            "extracted_json": payload.get("extracted_json") or {},
            "critiques": payload.get("critiques") or [],
            "revision_count": payload.get("revision_count", 0),
            "image_paths": payload.get("image_paths") if not (request.content_type and "multipart/form-data" in request.content_type) else payload_images,
        }
        
        # Start background thread
        thread = threading.Thread(
            target=_run_workflow_async,
            args=(job_id, initial_state),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "status": JobStatus.QUEUED.value
        }), 202  # 202 Accepted
        
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to submit workflow job", exc_info=True)
        return jsonify({"error": str(exc)}), 500


@app.route("/workflow/status/<job_id>", methods=["GET"])
def get_workflow_status(job_id: str):
    """Get the status of a workflow job.
    
    Args:
        job_id: Job identifier from /workflow/submit.
    
    Response (PENDING/PROCESSING):
        {
            "job_id": "uuid-string",
            "status": "PENDING" | "PROCESSING",
            "current_step": "Cartographer" | "Critic" | "Saver" | null,
            "progress": 0.0-1.0,
            "created_at": "ISO timestamp",
            "started_at": "ISO timestamp" | null
        }
    
    Response (COMPLETED):
        {
            "job_id": "uuid-string",
            "status": "SUCCEEDED",
            "result": {
                "raw_text": str,
                "extracted_json": {
                    "triples": [...]
                },
                ...
            },
            "progress": 1.0,
            "completed_at": "ISO timestamp"
        }
    
    Response (FAILED):
        {
            "job_id": "uuid-string",
            "status": "FAILED",
            "error": "error message",
            "completed_at": "ISO timestamp"
        }
    """
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    status = job["status"]
    response = {
        "job_id": job["job_id"],
        "status": status.value if isinstance(status, JobStatus) else str(status),
        "progress_pct": round((job.get("progress") or 0.0) * 100, 1),
        "created_at": job["created_at"].isoformat() if hasattr(job.get("created_at"), "isoformat") else job.get("created_at"),
        "current_step": job.get("current_step"),
        "error": job.get("error"),
    }
    if job.get("started_at"):
        response["started_at"] = job["started_at"].isoformat() if hasattr(job["started_at"], "isoformat") else job["started_at"]
    if job.get("completed_at"):
        response["completed_at"] = job["completed_at"].isoformat() if hasattr(job["completed_at"], "isoformat") else job["completed_at"]
    return jsonify(response), 200


@app.route("/workflow/result/<job_id>", methods=["GET"])
def get_workflow_result(job_id: str):
    """Return final result if available, otherwise status."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    status = job["status"]
    if status in (JobStatus.QUEUED, JobStatus.RUNNING):
        return jsonify({
            "job_id": job_id,
            "status": status.value if isinstance(status, JobStatus) else str(status),
            "progress_pct": round((job.get("progress") or 0.0) * 100, 1),
        }), 202
    if status == JobStatus.FAILED:
        return jsonify({
            "job_id": job_id,
            "status": status.value if isinstance(status, JobStatus) else str(status),
            "error": job.get("error"),
        }), 500
    # SUCCEEDED
    return jsonify({
        "job_id": job_id,
        "status": status.value if isinstance(status, JobStatus) else str(status),
        "result": job.get("result", {}),
    })


@app.route("/workflow/process", methods=["POST"])
def run_workflow():
    """Run the Cartographer -> Critic workflow synchronously (legacy endpoint).
    
    This endpoint is kept for backward compatibility but may timeout on long jobs.
    For new code, use /workflow/submit and /workflow/status/{job_id} instead.
    
    Request body:
        {
            "raw_text": str (required),
            "pdf_path": str (optional),
            "extracted_json": dict (optional),
            "critiques": list (optional),
            "revision_count": int (optional)
        }
    
    Response:
        {
            "raw_text": str,
            "pdf_path": str,
            "extracted_json": {
                "triples": [...]
            },
            "critiques": list,
            "revision_count": int,
            "critic_status": str
        }
    """
    payload = request.json or {}
    raw_text = payload.get("raw_text") or ""
    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400

    initial_state: PaperState = {
        "raw_text": raw_text,
        "pdf_path": payload.get("pdf_path", ""),
        "extracted_json": payload.get("extracted_json") or {},
        "critiques": payload.get("critiques") or [],
        "revision_count": payload.get("revision_count", 0),
        "image_paths": payload.get("image_paths") or [],
    }

    try:
        job_id = create_job(initial_state, idempotency_key=payload.get("idempotency_key"))
        thread = threading.Thread(
            target=_run_workflow_async,
            args=(job_id, initial_state),
            daemon=True
        )
        thread.start()
        return jsonify({"job_id": job_id, "status": JobStatus.QUEUED.value}), 202
    except Exception as exc:  # noqa: BLE001
        logger.error("Workflow execution failed", exc_info=True)
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 8000)))
