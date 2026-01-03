"""
Event publish/subscribe service for job event streams.

Manages SSE connections and async event queues for real-time job updates.
Provides reset hooks for test isolation.
"""

import asyncio
import threading
from collections import defaultdict
from typing import Dict, Set, Any

from ...shared.logger import get_logger

logger = get_logger("orchestrator", __name__)

# SSE event streams: job_id -> set of active connections
_sse_connections: Dict[str, Set[threading.Event]] = defaultdict(set)
_sse_lock = threading.Lock()

# Async event queues: job_id -> asyncio.Queue
_event_queues: Dict[str, asyncio.Queue] = {}
_event_queues_lock = threading.Lock()


def notify_sse_clients(job_id: str, data: Dict[str, Any]) -> None:
    """Notify all SSE clients for a job about new data.
    
    Args:
        job_id: Job identifier.
        data: Event data to send.
    """
    with _sse_lock:
        events = _sse_connections.get(job_id, set()).copy()
    
    # Set event to notify waiting SSE streams
    for event in events:
        event.set()


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
    """Reset all event queues and connections (for tests).
    
    Clears all SSE connections and event queues to ensure test isolation.
    """
    with _sse_lock:
        _sse_connections.clear()
    
    with _event_queues_lock:
        _event_queues.clear()
    
    logger.debug("Event queues and connections reset")

