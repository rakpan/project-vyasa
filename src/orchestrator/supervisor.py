"""
LangGraph Supervisor node for Project Vyasa.

The Supervisor uses SGLang to make routing decisions and plan the next steps
in the research workflow. It connects to ArangoDB for memory operations.
"""

import json
import os
import logging
from typing import TypedDict, Annotated, Literal, Optional, List, Dict, Any
from enum import Enum

from langgraph.graph import StateGraph, END
import requests
from arango import ArangoClient
from arango.database import StandardDatabase
from arango.collection import StandardCollection

from ..shared.config import (
    get_cortex_url,
    get_drafter_url,
    get_memory_url,
    get_arango_password,
    ARANGODB_DB,
    ARANGODB_USER,
)
from ..shared.logger import get_logger
from ..shared.role_manager import RoleRegistry

logger = get_logger("orchestrator", __name__)

# Get service URLs from environment or config
CORTEX_URL = get_cortex_url()
DRAFTER_URL = get_drafter_url()
MEMORY_URL = get_memory_url()


class NextStep(str, Enum):
    """Valid next steps in the supervisor workflow."""
    QUERY_MEMORY = "QUERY_MEMORY"
    DRAFT_CONTENT = "DRAFT_CONTENT"
    FINISH = "FINISH"


class SupervisorState(TypedDict):
    """State managed by the LangGraph supervisor."""
    messages: Annotated[List[Dict[str, Any]], "List of messages in the conversation"]
    next_step: NextStep
    query_result: Optional[Dict[str, Any]]
    draft_content: Optional[str]
    plan: Optional[Dict[str, Any]]
    error: Optional[str]


class Supervisor:
    """LangGraph Supervisor node that routes between workflow steps."""
    
    def __init__(
        self,
        cortex_url: Optional[str] = None,
        drafter_url: Optional[str] = None,
        arango_url: Optional[str] = None,
        arango_db: Optional[str] = None,
        arango_user: Optional[str] = None,
        arango_password: Optional[str] = None
    ):
        """
        Initialize the Supervisor.
        
        Args:
            cortex_url: URL of the Cortex (SGLang) service endpoint.
                       If None, uses CORTEX_URL from environment/config.
            drafter_url: URL of the Drafter (Ollama) service endpoint.
                       If None, uses DRAFTER_URL from environment/config.
            arango_url: ArangoDB connection URL.
                       If None, uses MEMORY_URL from environment/config.
            arango_db: ArangoDB database name.
                      If None, uses ARANGODB_DB from environment/config.
            arango_user: ArangoDB username.
                        If None, uses ARANGODB_USER from environment/config.
            arango_password: ArangoDB password.
                            If None, uses get_arango_password() from environment/config.
        """
        self.cortex_url = cortex_url or CORTEX_URL
        self.drafter_url = drafter_url or DRAFTER_URL
        self.db: Optional[StandardDatabase] = None
        resolved_password = arango_password or get_arango_password()
        self.role_registry = RoleRegistry(
            arango_url or MEMORY_URL,
            arango_db or ARANGODB_DB,
            arango_user or ARANGODB_USER,
            resolved_password
        )
        self._init_arangodb(
            arango_url or MEMORY_URL,
            arango_db or ARANGODB_DB,
            arango_user or ARANGODB_USER,
            resolved_password
        )
    
    def _init_arangodb(
        self,
        arango_url: str,
        arango_db: str,
        arango_user: str,
        arango_password: str
    ) -> None:
        """Initialize ArangoDB connection and ensure collections exist.
        
        Creates the database if it doesn't exist and ensures required collections
        (entities, edges, documents) are available.
        
        Args:
            arango_url: ArangoDB connection URL (e.g., "http://graph:8529").
            arango_db: Database name (e.g., "project_vyasa").
            arango_user: ArangoDB username (e.g., "root").
            arango_password: ArangoDB password.
            
        Raises:
            ConnectionError: If ArangoDB connection fails.
            Exception: If database or collection creation fails.
        """
        try:
            client = ArangoClient(hosts=arango_url)
            # Connect to system database first
            sys_db = client.db("_system", username=arango_user, password=arango_password)
            
            # Create database if it doesn't exist
            if not sys_db.has_database(arango_db):
                sys_db.create_database(arango_db)
                logger.info(f"Created ArangoDB database: {arango_db}")
            
            # Connect to the target database
            self.db = client.db(arango_db, username=arango_user, password=arango_password)
            
            # Ensure collections exist
            self._ensure_collections()
            
            logger.info(f"Connected to ArangoDB at {arango_url}/{arango_db}")
        except Exception as e:
            logger.error(
                "Failed to connect to ArangoDB",
                extra={"payload": {"url": arango_url, "db": arango_db, "user": arango_user}},
                exc_info=True,
            )
            raise
    
    def _ensure_collections(self) -> None:
        """Ensure required ArangoDB collections exist.
        
        Creates the following collections if they don't exist:
        - entities: Document collection for graph nodes
        - edges: Edge collection for graph relationships
        - documents: Document collection for document metadata
        
        Does nothing if ArangoDB connection is not initialized.
        """
        if not self.db:
            return
        
        collections = ["entities", "edges", "documents"]
        
        for coll_name in collections:
            if not self.db.has_collection(coll_name):
                if coll_name == "edges":
                    self.db.create_collection(coll_name, edge=True)
                else:
                    self.db.create_collection(coll_name)
                logger.info(f"Created collection: {coll_name}")
    
    def route(self, state: SupervisorState) -> SupervisorState:
        """Route to the next step based on current state.
        
        Uses SGLang (Cortex) with constrained decoding (regex) to output valid JSON
        routing decisions. The routing decision is made by the "Supervisor" role,
        which is dynamically loaded from ArangoDB via RoleRegistry.
        
        The routing prompt includes conversation history (last 5 messages) and uses
        the Supervisor role's system prompt to determine the next step:
        - QUERY_MEMORY: Query the knowledge graph for information
        - DRAFT_CONTENT: Generate content using Drafter (Ollama)
        - FINISH: Complete the workflow
        
        Args:
            state: Current supervisor state containing messages and optional plan.
            
        Returns:
            Updated SupervisorState with next_step set to a NextStep enum value.
            If routing fails, next_step is set to FINISH and error is populated.
            
        Side Effects:
            - Logs routing decision at INFO level
            - Logs errors at ERROR level if Cortex call fails
        """
        try:
            # Build routing prompt
            messages = state.get("messages", [])
            last_message = messages[-1] if messages else {}
            
            prompt = self._build_routing_prompt(messages, last_message)
            
            # Use SGLang API with regex constraint to force valid JSON
            # Regex pattern for valid JSON with next_step field
            json_regex = r'\{\s*"next_step"\s*:\s*"(QUERY_MEMORY|DRAFT_CONTENT|FINISH)"\s*(?:,\s*"reasoning"\s*:\s*"[^"]*")?\s*\}'
            
            # Call Cortex (SGLang) API
            payload = {
                "prompt": prompt,
                "sampling_params": {
                    "temperature": 0.1,  # Low temperature for deterministic routing
                    "max_new_tokens": 512,
                    "stop": [],
                },
                "regex": json_regex,
            }
            
            try:
                response = requests.post(
                    f"{self.cortex_url}/generate",
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
            except Exception:
                logger.error(
                    "Cortex routing request failed",
                    extra={
                        "payload": {
                            "endpoint": f"{self.cortex_url}/generate",
                            "prompt_chars": len(prompt),
                            "temperature": payload["sampling_params"]["temperature"],
                        }
                    },
                    exc_info=True,
                )
                raise
            
            result = response.json()
            routing_text = result.get("text", "").strip()
            
            # Clean up markdown code blocks if present
            if routing_text.startswith("```"):
                lines = routing_text.split("\n")
                routing_text = "\n".join(lines[1:-1]) if len(lines) > 2 else routing_text
            
            routing_data = json.loads(routing_text)
            
            # Validate and set next_step
            next_step_str = routing_data.get("next_step", "FINISH")
            try:
                next_step = NextStep(next_step_str)
            except ValueError:
                logger.warning(f"Invalid next_step: {next_step_str}, defaulting to FINISH")
                next_step = NextStep.FINISH
            
            state["next_step"] = next_step
            state["plan"] = routing_data
            
            logger.info(f"Routing decision: {next_step.value}")
            
            return state
            
        except Exception as e:
            logger.error(f"Routing failed: {e}", exc_info=True)
            state["next_step"] = NextStep.FINISH
            state["error"] = str(e)
            return state
    
    def _build_routing_prompt(self, messages: List[Dict[str, Any]], last_message: Dict[str, Any]) -> str:
        """Build the routing prompt for SGLang using dynamic role.
        
        Fetches the "Supervisor" role from RoleRegistry and uses its system_prompt
        as the base instruction. Appends conversation history (last 5 messages) and
        the last message content to provide context for routing decisions.
        
        Args:
            messages: List of conversation messages (each with 'role' and 'content').
            last_message: The most recent message in the conversation.
            
        Returns:
            Formatted prompt string ready for SGLang API. The prompt includes:
            - Supervisor role system prompt
            - Conversation history (last 5 messages)
            - Last message content
            - JSON output format instructions
        """
        # Get supervisor role (or use default)
        supervisor_role = self.role_registry.get_role("Supervisor")
        
        message_history = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in messages[-5:]  # Last 5 messages for context
        ])
        
        # Use role's system prompt as base, then append context
        base_prompt = supervisor_role.system_prompt if supervisor_role.system_prompt else """You are the Supervisor for Project Vyasa, a research factory.

Your task is to decide the next step in the workflow based on the conversation history.

Available steps:
- QUERY_MEMORY: Query the knowledge graph (ArangoDB) for relevant information
- DRAFT_CONTENT: Generate draft content using the Worker (Ollama)
- FINISH: Complete the task and return results"""
        
        prompt = f"""{base_prompt}

Conversation history:
{message_history}

Last message: {last_message.get('content', '')}

Analyze the conversation and determine the next step. Consider:
- If information needs to be retrieved from memory, choose QUERY_MEMORY
- If content needs to be drafted or summarized, choose DRAFT_CONTENT
- If the task is complete, choose FINISH

Return a JSON object with this structure:
{{
  "next_step": "QUERY_MEMORY|DRAFT_CONTENT|FINISH",
  "reasoning": "Brief explanation of your decision"
}}

JSON:"""
        return prompt
    
    def query_memory(self, state: SupervisorState) -> SupervisorState:
        """Query the ArangoDB knowledge graph for relevant information.
        
        Executes an AQL query against the ArangoDB knowledge graph to find entities
        and relations matching the query text from the last message. The query searches
        entity names and descriptions for matches.
        
        Args:
            state: Current supervisor state containing messages with query text.
            
        Returns:
            Updated SupervisorState with query_result populated. The query_result
            contains:
            - entities: List of matching graph nodes
            - edges: List of matching graph edges
            - count: Total number of results
            
        Raises:
            ValueError: If ArangoDB is not initialized.
            Exception: If AQL query execution fails.
            
        Note:
            This is a placeholder implementation. Production should use more
            sophisticated queries (e.g., semantic search, graph traversal).
        """
        try:
            if not self.db:
                raise ValueError("ArangoDB not initialized")
            
            messages = state.get("messages", [])
            last_message = messages[-1] if messages else {}
            query_text = last_message.get("content", "")
            
            # Build AQL query to search entities and edges
            # This is a placeholder - in production, you'd use more sophisticated queries
            aql_query = """
            FOR entity IN entities
                FILTER entity.name LIKE @query OR entity.description LIKE @query
                LIMIT 10
                RETURN entity
            """
            
            cursor = self.db.aql.execute(
                aql_query,
                bind_vars={"query": f"%{query_text}%"}
            )
            
            results = list(cursor)
            
            # Also query edges
            edge_query = """
            FOR edge IN edges
                FILTER edge._from IN (
                    FOR entity IN entities
                        FILTER entity.name LIKE @query OR entity.description LIKE @query
                        RETURN entity._id
                )
                LIMIT 20
                RETURN edge
            """
            
            edge_cursor = self.db.aql.execute(
                edge_query,
                bind_vars={"query": f"%{query_text}%"}
            )
            
            edges = list(edge_cursor)
            
            state["query_result"] = {
                "entities": results,
                "edges": edges,
                "count": len(results)
            }
            
            logger.info(f"Query returned {len(results)} entities and {len(edges)} edges")
            
            return state
            
        except Exception as e:
            logger.error(f"Memory query failed: {e}", exc_info=True)
            state["error"] = str(e)
            state["query_result"] = {"entities": [], "edges": [], "count": 0}
            return state
    
    def draft_content(self, state: SupervisorState) -> SupervisorState:
        """Draft content using the Drafter (Ollama) service.
        
        Generates prose, summaries, or creative content based on the conversation
        history and query results. This is a placeholder implementation that will
        be replaced with actual Ollama API calls in production.
        
        Args:
            state: Current supervisor state containing messages and optional query_result.
            
        Returns:
            Updated SupervisorState with draft_content populated. The draft_content
            contains generated text based on the context.
            
        Note:
            This is a placeholder implementation. Production should:
            - Call Ollama API at self.drafter_url
            - Use conversation history as context
            - Generate appropriate content based on query results
            - Handle errors gracefully
        """
        # Placeholder for Ollama (Drafter) integration
        # In production, this would make an HTTP request to Ollama at self.drafter_url
        messages = state.get("messages", [])
        query_result = state.get("query_result", {})
        
        # For now, return a placeholder
        state["draft_content"] = f"[Draft content based on {len(query_result.get('entities', []))} entities]"
        
        logger.info(f"Draft content generated (placeholder) - Drafter URL: {self.drafter_url}")
        
        return state
    
    def should_continue(self, state: SupervisorState) -> Literal["query_memory", "draft_content", "finish"]:
        """Determine which node to execute next based on next_step.
        
        This is a conditional edge function used by LangGraph to route the workflow
        after the supervisor node. It maps the NextStep enum value to the corresponding
        node name in the graph.
        
        Args:
            state: Current supervisor state with next_step set by route() method.
            
        Returns:
            Literal string indicating the next node to execute:
            - "query_memory": If next_step is QUERY_MEMORY
            - "draft_content": If next_step is DRAFT_CONTENT
            - "finish": If next_step is FINISH or invalid
            
        Note:
            This function is used by LangGraph's add_conditional_edges() method.
            The return value must match one of the keys in the edge mapping.
        """
        next_step = state.get("next_step", NextStep.FINISH)
        
        if next_step == NextStep.QUERY_MEMORY:
            return "query_memory"
        elif next_step == NextStep.DRAFT_CONTENT:
            return "draft_content"
        else:
            return "finish"
    
    def build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow graph.
        
        Returns:
            Configured StateGraph
        """
        workflow = StateGraph(SupervisorState)
        
        # Add nodes
        workflow.add_node("supervisor", self.route)
        workflow.add_node("query_memory", self.query_memory)
        workflow.add_node("draft_content", self.draft_content)
        
        # Set entry point
        workflow.set_entry_point("supervisor")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "supervisor",
            self.should_continue,
            {
                "query_memory": "query_memory",
                "draft_content": "draft_content",
                "finish": END
            }
        )
        
        # After query_memory or draft_content, return to supervisor
        workflow.add_edge("query_memory", "supervisor")
        workflow.add_edge("draft_content", "supervisor")
        
        return workflow


def create_supervisor(
    cortex_url: Optional[str] = None,
    drafter_url: Optional[str] = None,
    arango_url: Optional[str] = None,
    arango_db: Optional[str] = None,
    arango_user: Optional[str] = None,
    arango_password: Optional[str] = None
) -> Supervisor:
    """
    Factory function to create a Supervisor instance.
    
    Args:
        cortex_url: URL of the Cortex (SGLang) service endpoint.
                   If None, uses CORTEX_URL from environment/config.
        drafter_url: URL of the Drafter (Ollama) service endpoint.
                    If None, uses DRAFTER_URL from environment/config.
        arango_url: ArangoDB connection URL.
                   If None, uses MEMORY_URL from environment/config.
        arango_db: ArangoDB database name.
                  If None, uses ARANGODB_DB from environment/config.
        arango_user: ArangoDB username.
                    If None, uses ARANGODB_USER from environment/config.
        arango_password: ArangoDB password.
                        If None, uses get_arango_password() from environment/config.
        
    Returns:
        Initialized Supervisor instance
    """
    return Supervisor(
        cortex_url=cortex_url,
        drafter_url=drafter_url,
        arango_url=arango_url,
        arango_db=arango_db,
        arango_user=arango_user,
        arango_password=arango_password
    )
