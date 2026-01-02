"""
Workflow loop routing tests.
"""

from ...orchestrator.workflow import _critic_router
from ...orchestrator.state import ResearchState


def test_router_stops_after_max_retries():
    """When failures exceed the retry budget, workflow should go to saver."""
    state: ResearchState = {"critic_status": "fail", "revision_count": 3, "jobId": "j1", "threadId": "j1"}
    route = _critic_router(state)
    assert route == "manual"
