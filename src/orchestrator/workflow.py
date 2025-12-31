"""
Agentic workflow wiring for Project Vyasa using LangGraph.
"""

from langgraph.graph import StateGraph, END

from .state import PaperState
from .nodes import (
    cartographer_node,
    critic_node,
    reframing_node,
    saver_node,
    synthesizer_node,
    failure_cleanup_node,
    vision_node,
    lead_counsel_node,
    logician_node,
)
from .normalize import normalize_extracted_json


def _critic_router(state: PaperState) -> str:
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
    graph = StateGraph(PaperState)

    graph.add_node("vision", vision_node)
    graph.add_node("cartographer", cartographer_node)
    graph.add_node("lead_counsel", lead_counsel_node)
    graph.add_node("logician", logician_node)
    graph.add_node("critic", critic_node)
    graph.add_node("reframing", reframing_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("saver", saver_node)
    graph.add_node("failure_cleanup", failure_cleanup_node)

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
        lambda state: "failure_cleanup" if state.get("force_failure_cleanup") else "saver",
        {
            "saver": "saver",
            "failure_cleanup": "failure_cleanup",
        },
    )
    graph.add_edge("saver", END)
    graph.add_edge("failure_cleanup", END)

    compiled = graph.compile()

    # Create a wrapper class that normalizes extracted_json after invocation
    class NormalizedWorkflow:
        """Wrapper around CompiledStateGraph that normalizes extracted_json."""
        
        def __init__(self, compiled_graph):
            self._compiled = compiled_graph
        
        def invoke(self, state):
            """Invoke the workflow and normalize extracted_json in the result."""
            result_state = self._compiled.invoke(state)
            if "extracted_json" in result_state:
                result_state["extracted_json"] = normalize_extracted_json(result_state["extracted_json"])
            return result_state
        
        def stream(self, state):
            """Stream the workflow execution."""
            return self._compiled.stream(state)
        
        def __getattr__(self, name):
            """Delegate other attributes to the compiled graph."""
            return getattr(self._compiled, name)

    return NormalizedWorkflow(compiled)
