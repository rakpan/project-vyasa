"""
Agentic workflow wiring for Project Vyasa using LangGraph.
"""

from langgraph.graph import StateGraph, END
# LangGraph 0.3.x exposes RetryPolicy in langgraph.types; keep a fallback for older layouts.
try:
    from langgraph.types import RetryPolicy
except ImportError:  # pragma: no cover - compatibility shim
    from langgraph.graph import RetryPolicy  # type: ignore

from .state import ResearchState
from .nodes import (
    cartographer_node,
    critic_node,
    reframing_node,
    artifact_registry_node,
    tone_validator_node,
    saver_node,
    synthesizer_node,
    failure_cleanup_node,
    vision_node,
    lead_counsel_node,
    logician_node,
)
from .normalize import normalize_extracted_json
from ..shared.config import get_checkpoint_saver

def _critic_router(state: ResearchState) -> str:
    """Route based on critic status and revision budget."""
    if state.get("force_failure_cleanup"):
        return "manual"
    status = (state.get("critic_status") or "fail").lower()
    revisions = state.get("revision_count", 0)
    if status == "pass":
        return "pass"
    if revisions < 3:
        return "retry"
    return "manual"


def build_workflow():
    """Compile the Cartographer -> Critic loop with optional counsel/logician path."""
    graph = StateGraph(ResearchState)

    graph.add_node("vision", vision_node, retry_policy=RetryPolicy(max_attempts=3), interrupt_before=[])
    graph.add_node("cartographer", cartographer_node, interrupt_before=[])
    graph.add_node("lead_counsel", lead_counsel_node, interrupt_before=[])
    graph.add_node("logician", logician_node, retry_policy=RetryPolicy(max_attempts=3), interrupt_before=[])
    graph.add_node("critic", critic_node, interrupt_before=[])
    graph.add_node("reframing", reframing_node, interrupt_before=["reframing"])
    graph.add_node("synthesizer", synthesizer_node, interrupt_before=[])
    # Governance: tone guard must run before tables/manuscript persistence
    try:
        from .nodes.tone_guard import tone_linter_node
        graph.add_node("tone_guard", tone_linter_node, interrupt_before=[])
    except Exception:
        graph.add_node("tone_guard", lambda state: state, interrupt_before=[])
    # Governance: precision validation should happen after tables are drafted (embedded in manifest builder)
    graph.add_node("artifact_registry", artifact_registry_node, interrupt_before=[])
    graph.add_node("tone_validator", tone_validator_node, interrupt_before=[])
    graph.add_node("saver", saver_node, interrupt_before=[])
    graph.add_node("failure_cleanup", failure_cleanup_node, interrupt_before=[])

    graph.set_entry_point("vision")
    graph.add_edge("vision", "cartographer")
    graph.add_conditional_edges(
        "cartographer",
        lambda state: "failure_cleanup" if state.get("force_failure_cleanup") else ("lead_counsel" if (state.get("extracted_json") or {}).get("triples") else "critic"),
        {
            "lead_counsel": "lead_counsel",
            "critic": "critic",
            "failure_cleanup": "failure_cleanup",
        },
    )
    graph.add_conditional_edges(
        "lead_counsel",
        lambda state: "logician" if (state.get("lead_counsel") or {}).get("presentation") == "DETAIL" else "critic",
        {
            "logician": "logician",
            "critic": "critic",
        },
    )
    graph.add_edge("logician", "critic")
    graph.add_conditional_edges(
        "critic",
        _critic_router,
        {
            "reframing": "reframing",
            "pass": "synthesizer",
            "retry": "cartographer",
            "manual": "failure_cleanup",
        },
    )
    graph.add_conditional_edges(
        "reframing",
        lambda state: "failure_cleanup" if state.get("needs_signoff") else "saver",
        {
            "failure_cleanup": "failure_cleanup",
            "saver": "saver",
        },
    )
    graph.add_conditional_edges(
        "synthesizer",
        lambda state: "failure_cleanup" if state.get("force_failure_cleanup") else "tone_guard",
        {
            "tone_guard": "tone_guard",
            "failure_cleanup": "failure_cleanup",
        },
    )
    graph.add_edge("tone_guard", "artifact_registry")
    graph.add_edge("tone_guard", "tone_validator")
    graph.add_edge("tone_validator", "saver")
    graph.add_edge("saver", END)
    graph.add_edge("failure_cleanup", END)

    checkpointer = get_checkpoint_saver()
    compiled = graph.compile(checkpointer=checkpointer)

    # Create a wrapper class that normalizes extracted_json after invocation
    class NormalizedWorkflow:
        """Wrapper around CompiledStateGraph that normalizes extracted_json."""
        
        def __init__(self, compiled_graph):
            self._compiled = compiled_graph

        @staticmethod
        def _thread_config(state, override_config=None):
            if override_config:
                return override_config
            thread_id = None
            if isinstance(state, dict):
                thread_id = state.get("threadId") or state.get("job_id") or state.get("jobId")
            return {"configurable": {"thread_id": thread_id}}
        
        def invoke(self, state):
            config = self._thread_config(state)
            result_state = self._compiled.invoke(state, config=config)
            if "extracted_json" in result_state:
                result_state["extracted_json"] = normalize_extracted_json(result_state["extracted_json"])
            return result_state
        
        def stream(self, state):
            config = self._thread_config(state)
            return self._compiled.stream(state, config=config)

        def astream_events(self, state, config=None, version="v2"):
            """Event streaming passthrough for LangGraph 1.x."""
            cfg = self._thread_config(state, override_config=config)
            return self._compiled.astream_events(state, config=cfg, version=version)

        def __getattr__(self, name):
            return getattr(self._compiled, name)

    return NormalizedWorkflow(compiled)
