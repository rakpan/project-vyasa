"""
Research metrics computation for sideload/reprocess lifecycle KPIs.

Provides internal functions to compute key performance indicators:
- Sideload backlog and velocity
- Promotion rates
- Reprocess success rates and cycle times
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from arango import ArangoClient

from ...shared.config import get_memory_url, ARANGODB_DB, ARANGODB_USER, get_arango_password
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

EXTERNAL_REFERENCES_COLLECTION = "external_references"
JOBS_COLLECTION = "jobs"


def _get_db():
    """Get ArangoDB database connection."""
    try:
        client = ArangoClient(hosts=get_memory_url())
        return client.db(ARANGODB_DB, username=ARANGODB_USER, password=get_arango_password())
    except Exception as e:
        logger.warning(f"Failed to connect to database for research metrics: {e}")
        return None


def compute_research_metrics() -> Dict[str, Any]:
    """Compute research lifecycle KPIs.
    
    Returns:
        Dictionary with metrics:
        - sideload_backlog: int
        - sideload_velocity_24h: int
        - promotion_rate_24h: float (0.0-1.0)
        - reprocess_success_rate_24h: float (0.0-1.0)
        - avg_reprocess_cycle_time_ms: float (average in milliseconds)
    """
    db = _get_db()
    if not db:
        return {
            "sideload_backlog": 0,
            "sideload_velocity_24h": 0,
            "promotion_rate_24h": 0.0,
            "reprocess_success_rate_24h": 0.0,
            "avg_reprocess_cycle_time_ms": 0.0,
            "error": "Database unavailable",
        }
    
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    metrics = {}
    
    try:
        # 1. Sideload backlog (INGESTED, EXTRACTING, NEEDS_REVIEW)
        if db.has_collection(EXTERNAL_REFERENCES_COLLECTION):
            backlog_query = f"""
            FOR ref IN {EXTERNAL_REFERENCES_COLLECTION}
            FILTER ref.status IN ["INGESTED", "EXTRACTING", "NEEDS_REVIEW"]
            RETURN ref
            """
            cursor = db.aql.execute(backlog_query)
            backlog_refs = list(cursor)
            metrics["sideload_backlog"] = len(backlog_refs)
        else:
            metrics["sideload_backlog"] = 0
        
        # 2. Sideload velocity (EXTRACTED in last 24h)
        # Note: Using string comparison for ISO8601 dates (works for lexicographic ordering)
        if db.has_collection(EXTERNAL_REFERENCES_COLLECTION):
            cutoff_iso = twenty_four_hours_ago.isoformat()
            velocity_query = f"""
            FOR ref IN {EXTERNAL_REFERENCES_COLLECTION}
            FILTER ref.status == "EXTRACTED"
            FILTER ref.extracted_at >= @cutoff
            RETURN ref
            """
            cursor = db.aql.execute(
                velocity_query,
                bind_vars={"cutoff": cutoff_iso}
            )
            extracted_refs = list(cursor)
            metrics["sideload_velocity_24h"] = len(extracted_refs)
        else:
            metrics["sideload_velocity_24h"] = 0
        
        # 3. Promotion rate (PROMOTED / EXTRACTED in last 24h)
        if db.has_collection(EXTERNAL_REFERENCES_COLLECTION):
            cutoff_iso = twenty_four_hours_ago.isoformat()
            promotion_query = f"""
            FOR ref IN {EXTERNAL_REFERENCES_COLLECTION}
            FILTER ref.status IN ["EXTRACTED", "PROMOTED"]
            FILTER ref.extracted_at >= @cutoff
            RETURN ref
            """
            cursor = db.aql.execute(
                promotion_query,
                bind_vars={"cutoff": cutoff_iso}
            )
            refs = list(cursor)
            extracted_count = sum(1 for r in refs if r.get("status") == "EXTRACTED")
            promoted_count = sum(1 for r in refs if r.get("status") == "PROMOTED")
            
            # Promotion rate: promoted / (extracted + promoted)
            total_relevant = extracted_count + promoted_count
            metrics["promotion_rate_24h"] = (promoted_count / total_relevant) if total_relevant > 0 else 0.0
        else:
            metrics["promotion_rate_24h"] = 0.0
        
        # 4. Reprocess success rate and cycle time (jobs with parent_job_id in last 24h)
        if db.has_collection(JOBS_COLLECTION):
            cutoff_iso = twenty_four_hours_ago.isoformat()
            reprocess_query = f"""
            FOR job IN {JOBS_COLLECTION}
            FILTER job.parent_job_id != null
            FILTER job.created_at >= @cutoff
            RETURN job
            """
            cursor = db.aql.execute(
                reprocess_query,
                bind_vars={"cutoff": cutoff_iso}
            )
            reprocess_jobs = list(cursor)
            
            requested_count = len(reprocess_jobs)
            completed_count = sum(
                1 for j in reprocess_jobs
                if j.get("status") in ("SUCCEEDED", "FINALIZED", "completed")
            )
            
            metrics["reprocess_success_rate_24h"] = (completed_count / requested_count) if requested_count > 0 else 0.0
            
            # Calculate average cycle time (completed_at - created_at)
            cycle_times = []
            for job in reprocess_jobs:
                if job.get("completed_at") and job.get("created_at"):
                    try:
                        created = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
                        completed = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
                        cycle_time_ms = (completed - created).total_seconds() * 1000
                        if cycle_time_ms > 0:
                            cycle_times.append(cycle_time_ms)
                    except (ValueError, TypeError):
                        continue
            
            if cycle_times:
                metrics["avg_reprocess_cycle_time_ms"] = sum(cycle_times) / len(cycle_times)
            else:
                metrics["avg_reprocess_cycle_time_ms"] = 0.0
        else:
            metrics["reprocess_success_rate_24h"] = 0.0
            metrics["avg_reprocess_cycle_time_ms"] = 0.0
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to compute research metrics: {e}", exc_info=True)
        return {
            "sideload_backlog": 0,
            "sideload_velocity_24h": 0,
            "promotion_rate_24h": 0.0,
            "reprocess_success_rate_24h": 0.0,
            "avg_reprocess_cycle_time_ms": 0.0,
            "error": str(e),
        }

