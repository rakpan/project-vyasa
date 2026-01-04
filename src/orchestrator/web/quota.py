"""
Firecrawl Cloud quota tracking and enforcement.

Tracks monthly usage in ArangoDB to enforce free-tier limits (500/month).
"""

from datetime import datetime, timezone
from typing import Optional
from arango.database import StandardDatabase

from ...shared.config import _env
from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# Configuration
FIRECRAWL_MONTHLY_QUOTA = int(_env("FIRECRAWL_MONTHLY_QUOTA", "500"))
WEB_USAGE_COLLECTION = "web_usage"


def _get_month_key() -> str:
    """Get current month key in YYYY-MM format.
    
    Returns:
        Month key string (e.g., "2025-01")
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def can_spend(db: StandardDatabase, n: int = 1) -> bool:
    """Check if quota allows spending n requests.
    
    Args:
        db: ArangoDB database instance
        n: Number of requests to check (default: 1)
    
    Returns:
        True if quota allows spending n requests, False otherwise
    """
    if not db:
        logger.warning("ArangoDB unavailable for quota check; allowing spend")
        return True
    
    try:
        month_key = _get_month_key()
        
        # Ensure collection exists
        if not db.has_collection(WEB_USAGE_COLLECTION):
            db.create_collection(WEB_USAGE_COLLECTION)
        
        collection = db.collection(WEB_USAGE_COLLECTION)
        
        # Get or create usage record for current month
        try:
            doc = collection.get(month_key)
            requests_used = doc.get("requests_used", 0)
        except Exception:
            # Document doesn't exist, create it
            requests_used = 0
        
        # Check if spending n would exceed quota
        can_spend_result = (requests_used + n) <= FIRECRAWL_MONTHLY_QUOTA
        
        if not can_spend_result:
            logger.warning(
                f"Quota check failed: {requests_used}/{FIRECRAWL_MONTHLY_QUOTA} used, "
                f"requested {n} would exceed quota"
            )
        
        return can_spend_result
        
    except Exception as e:
        logger.error(f"Failed to check quota: {e}", exc_info=True)
        # Fail open: allow spend if quota check fails
        return True


def record_spend(db: StandardDatabase, n: int = 1) -> bool:
    """Record spending n requests in quota tracker.
    
    Args:
        db: ArangoDB database instance
        n: Number of requests to record (default: 1)
    
    Returns:
        True if recorded successfully, False otherwise
    """
    if not db:
        logger.warning("ArangoDB unavailable for quota recording; skipping")
        return False
    
    try:
        month_key = _get_month_key()
        
        # Ensure collection exists
        if not db.has_collection(WEB_USAGE_COLLECTION):
            db.create_collection(WEB_USAGE_COLLECTION)
        
        collection = db.collection(WEB_USAGE_COLLECTION)
        
        # Get or create usage record for current month
        try:
            doc = collection.get(month_key)
            requests_used = doc.get("requests_used", 0)
        except Exception:
            # Document doesn't exist, create it
            requests_used = 0
        
        # Update usage
        new_requests_used = requests_used + n
        now = datetime.now(timezone.utc).isoformat()
        
        collection.update(
            {
                "_key": month_key,
                "requests_used": new_requests_used,
                "last_updated": now,
            },
            merge=True,
        )
        
        logger.info(
            f"Recorded {n} request(s) in quota: {new_requests_used}/{FIRECRAWL_MONTHLY_QUOTA} used",
            extra={
                "payload": {
                    "month": month_key,
                    "requests_used": new_requests_used,
                    "quota": FIRECRAWL_MONTHLY_QUOTA,
                    "spent": n,
                }
            },
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to record quota spend: {e}", exc_info=True)
        return False


def get_usage(db: StandardDatabase) -> Optional[dict]:
    """Get current month's usage statistics.
    
    Args:
        db: ArangoDB database instance
    
    Returns:
        Dictionary with usage stats or None if unavailable:
        - month: Month key (YYYY-MM)
        - requests_used: Number of requests used
        - quota: Monthly quota limit
        - remaining: Remaining requests
    """
    if not db:
        return None
    
    try:
        month_key = _get_month_key()
        
        if not db.has_collection(WEB_USAGE_COLLECTION):
            return {
                "month": month_key,
                "requests_used": 0,
                "quota": FIRECRAWL_MONTHLY_QUOTA,
                "remaining": FIRECRAWL_MONTHLY_QUOTA,
            }
        
        collection = db.collection(WEB_USAGE_COLLECTION)
        
        try:
            doc = collection.get(month_key)
            requests_used = doc.get("requests_used", 0)
        except Exception:
            requests_used = 0
        
        return {
            "month": month_key,
            "requests_used": requests_used,
            "quota": FIRECRAWL_MONTHLY_QUOTA,
            "remaining": max(0, FIRECRAWL_MONTHLY_QUOTA - requests_used),
        }
        
    except Exception as e:
        logger.error(f"Failed to get usage stats: {e}", exc_info=True)
        return None

