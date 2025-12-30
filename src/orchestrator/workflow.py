"""
Agentic workflow wiring for Project Vyasa using LangGraph.
"""

from langgraph.graph import StateGraph, END

from .state import PaperState
from .nodes import cartographer_node, critic_node, saver_node, vision_node
from .normalize import normalize_extracted_json


def _critic_router(state: PaperState) -> str:
    """Route based on critic status and revision budget."""
    status = (state.get("critic_status") or "fail").lower()
    revisions = state.get("revision_count", 0)
    if status == "pass":
        return "pass"
    if revisions < 3:
        return "retry"
    return "manual"


def build_workflow():
    """Compile the Cartographer -> Critic loop with saver terminal."""
    graph = StateGraph(PaperState)

    graph.add_node("vision", vision_node)
    graph.add_node("cartographer", cartographer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("saver", saver_node)

    graph.set_entry_point("vision")
    graph.add_edge("vision", "cartographer")
    graph.add_edge("cartographer", "critic")
    graph.add_conditional_edges(
        "critic",
        _critic_router,
        {
            "pass": "saver",
            "retry": "cartographer",
            "manual": "saver",
        },
    )
    graph.add_edge("saver", END)

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
