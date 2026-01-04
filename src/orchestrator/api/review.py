"""
Review Queue API endpoints for Project Vyasa.

Provides endpoints for fetching and managing ReviewTasks from the governance queue.
"""

from flask import Blueprint, jsonify, request
from arango import ArangoClient
from arango.database import StandardDatabase
from typing import List, Dict, Any, Optional

from ...shared.config import (
    get_memory_url,
    get_arango_password,
    ARANGODB_DB,
    ARANGODB_USER,
)
from ...shared.logger import get_logger
from ..schemas.review import ReviewTask, ReviewStatus

logger = get_logger("orchestrator", __name__)

review_bp = Blueprint("review", __name__)

REVIEW_TASKS_COLLECTION = "review_tasks"


def _get_db() -> Optional[StandardDatabase]:
    """Get ArangoDB database connection."""
    try:
        client = ArangoClient(hosts=get_memory_url())
        return client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
    except Exception as e:
        logger.warning(f"Failed to connect to database for review API: {e}")
        return None


@review_bp.route("/api/review-tasks", methods=["GET"])
def list_review_tasks():
    """List ReviewTasks for a project.
    
    Query parameters:
        project_id (required): Project ID to filter by
        status (optional): Filter by status (PENDING, APPROVED, REJECTED, etc.)
        limit (optional): Maximum number of tasks to return (default: 50)
    
    Returns:
        JSON response with list of ReviewTasks
    """
    project_id = request.args.get("project_id")
    status_filter = request.args.get("status")
    limit = int(request.args.get("limit", 50))
    
    if not project_id:
        return jsonify({"error": "project_id is required"}), 400
    
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        # Ensure collection exists
        if not db.has_collection(REVIEW_TASKS_COLLECTION):
            return jsonify({"tasks": []}), 200
        
        collection = db.collection(REVIEW_TASKS_COLLECTION)
        
        # Build AQL query
        query = f"""
        FOR task IN {REVIEW_TASKS_COLLECTION}
        FILTER task.project_id == @project_id
        """
        
        bind_vars = {"project_id": project_id}
        
        if status_filter:
            query += " FILTER task.status == @status"
            bind_vars["status"] = status_filter
        
        query += """
        SORT task.created_at DESC
        LIMIT @limit
        RETURN task
        """
        bind_vars["limit"] = limit
        
        cursor = db.aql.execute(query, bind_vars=bind_vars)
        tasks = list(cursor)
        
        # Convert to ReviewTask models for validation
        review_tasks = []
        for task_doc in tasks:
            try:
                # Remove ArangoDB internal fields
                task_doc.pop("_id", None)
                task_doc.pop("_key", None)
                task_doc.pop("_rev", None)
                
                # Parse ReviewTask
                review_task = ReviewTask(**task_doc)
                review_tasks.append(review_task.model_dump(mode="json"))
            except Exception as e:
                logger.warning(f"Failed to parse ReviewTask: {e}", exc_info=True)
                continue
        
        return jsonify({"tasks": review_tasks}), 200
        
    except Exception as e:
        logger.error(f"Failed to list review tasks: {e}", exc_info=True)
        return jsonify({"error": f"Failed to list review tasks: {e}"}), 500


@review_bp.route("/api/review-tasks/<review_id>", methods=["GET"])
def get_review_task(review_id: str):
    """Get a single ReviewTask by ID.
    
    Args:
        review_id: Review task ID
    
    Returns:
        JSON response with ReviewTask
    """
    db = _get_db()
    if not db:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        if not db.has_collection(REVIEW_TASKS_COLLECTION):
            return jsonify({"error": "Review task not found"}), 404
        
        collection = db.collection(REVIEW_TASKS_COLLECTION)
        
        try:
            task_doc = collection.get(review_id)
        except Exception:
            return jsonify({"error": "Review task not found"}), 404
        
        if not task_doc:
            return jsonify({"error": "Review task not found"}), 404
        
        # Remove ArangoDB internal fields
        task_doc.pop("_id", None)
        task_doc.pop("_key", None)
        task_doc.pop("_rev", None)
        
        # Parse ReviewTask
        review_task = ReviewTask(**task_doc)
        
        return jsonify(review_task.model_dump(mode="json")), 200
        
    except Exception as e:
        logger.error(f"Failed to get review task {review_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to get review task: {e}"}), 500

