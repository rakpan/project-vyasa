"""
Event publish/subscribe service for job event streams.

Manages async event queues for real-time job updates via Server-Sent Events (SSE).
Provides reset hooks for test isolation.
"""

import asyncio
import threading
from typing import Dict, Any

from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# Async event queues: job_id -> asyncio.Queue
_event_queues: Dict[str, asyncio.Queue] = {}
_event_queues_lock = threading.Lock()


def publish_event(job_id: str, payload: Dict[str, Any]) -> None:
    """Publish an event to async subscribers (event stream) without blocking.
    
    Args:
        job_id: Job identifier.
        payload: Event payload to publish.
    """
    with _event_queues_lock:
        queue = _event_queues.get(job_id)
    if queue:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.debug(f"Event queue full for {job_id}, dropping event")
        except Exception:
            logger.debug("Unexpected error publishing event", exc_info=True)


def get_event_queue(job_id: str) -> asyncio.Queue:
    """Get or create an event queue for a job.
    
    Args:
        job_id: Job identifier.
    
    Returns:
        asyncio.Queue instance for the job.
    """
    with _event_queues_lock:
        queue = _event_queues.get(job_id)
        if queue is None:
            queue = asyncio.Queue(maxsize=100)
            _event_queues[job_id] = queue
        return queue


def remove_event_queue(job_id: str) -> None:
    """Remove an event queue for a job (cleanup).
    
    Args:
        job_id: Job identifier.
    """
    with _event_queues_lock:
        _event_queues.pop(job_id, None)


def reset_events() -> None:
    """Reset all event queues (for tests).
    
    Clears all event queues to ensure test isolation.
    """
    with _event_queues_lock:
        _event_queues.clear()
    
    logger.debug("Event queues reset")


def reset_for_tests() -> None:
    """Reset all event queues and SSE state (for test isolation).
    
    This is an alias for reset_events() with a more explicit name for test fixtures.
    Clears all event queues to prevent state leakage between tests.
    
    Safe to call in production (no-op if no queues exist), but intended for test teardown.
    """
    reset_events()

