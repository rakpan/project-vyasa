# Project Vyasa Source Code

This directory contains the core logic for Project Vyasa, a high-performance research factory on NVIDIA DGX.

## Structure

```
src/
├── shared/
│   ├── __init__.py
│   └── schema.py          # Pydantic models for knowledge graph
├── ingestion/
│   ├── __init__.py
│   └── extractor.py        # SGLang-optimized extraction
├── orchestrator/
│   ├── __init__.py
│   └── supervisor.py       # LangGraph Supervisor node
└── requirements.txt        # Python dependencies
```

## Modules

### `shared/schema.py`

Defines Pydantic models for the knowledge graph:
- **Entities**: `Vulnerability`, `Mechanism`, `Constraint`, `Outcome`
- **Relations**: `MITIGATES`, `ENABLES`, `REQUIRES` (via `RelationType` enum)
- **GraphTriple**: Represents subject-predicate-object triples
- **KnowledgeGraph**: Complete extraction result container

All models are type-safe and validated using Pydantic v2.

### `ingestion/extractor.py`

SGLang-optimized extraction function that:
- Connects to Cortex (SGLang) service via `CORTEX_URL` environment variable
- Uses regex constraints to enforce strict JSON schema compliance
- Supports batch processing
- Returns validated `KnowledgeGraph` objects

**Usage:**
```python
from src.ingestion import extract_knowledge_graph

result = extract_knowledge_graph(text="Your research text here", source="document_id")
```

### `orchestrator/supervisor.py`

LangGraph Supervisor node that:
- Routes between `QUERY_MEMORY`, `DRAFT_CONTENT`, and `FINISH` steps
- Uses SGLang for routing decisions with constrained JSON output
- Connects to ArangoDB for knowledge graph queries
- Manages workflow state via `SupervisorState`

**Usage:**
```python
from src.orchestrator import create_supervisor

supervisor = create_supervisor()
graph = supervisor.build_graph()
app = graph.compile()
```

## Dependencies

Install dependencies:
```bash
pip install -r src/requirements.txt
```

Key dependencies:
- `pydantic>=2.0.0` - Type validation
- `langgraph>=0.0.20` - Workflow orchestration
- `python-arango>=7.0.0` - ArangoDB client
- `requests>=2.31.0` - HTTP client for SGLang

## Environment Variables

Set these in your DGX environment or docker-compose.yml:

```bash
# Service URLs (Functional Naming)
CORTEX_URL=http://vyasa-cortex:30000          # Cortex (SGLang) - Logic & Extraction
CORTEX_SERVICE_URL=http://vyasa-cortex:30000  # Alias
DRAFTER_URL=http://vyasa-drafter:11434        # Drafter (Ollama) - Chat & Prose
WORKER_URL=http://vyasa-drafter:11434         # Alias (backward compatibility)
MEMORY_URL=http://graph:8529           # Graph (ArangoDB) - Knowledge Graph
MEMORY_SERVICE_URL=http://graph:8529   # Alias
ARANGODB_URL=http://graph:8529        # Alias
VECTOR_URL=http://vyasa-qdrant:6333           # Vector (Qdrant) - Search Index
QDRANT_URL=http://vyasa-qdrant:6333           # Alias
EMBEDDER_URL=http://vyasa-embedder:80         # Embedder (Sentence Transformers)
SENTENCE_TRANSFORMER_URL=http://vyasa-embedder:80  # Alias

# Database Configuration
ARANGODB_DB=project_vyasa
ARANGODB_USER=root
ARANGODB_PASSWORD=your_password
```

**Note:** All services use environment variables from `src/shared/config.py`. The code is agnostic to container names and will query Docker for service locations via environment variables.

## Architecture Notes

1. **Strict JSON**: All extraction uses SGLang's regex constraints - no "prompt and pray"
2. **Type Safety**: All entities use Pydantic models
3. **Graph-First**: State is written to ArangoDB immediately, not stored in variables
4. **No Hallucinations**: All claims reference specific `_id` from the Knowledge Graph

## SGLang API Notes

The code uses HTTP requests to the SGLang supervisor. If your SGLang deployment uses a different API format, adjust the payload structure in:
- `src/ingestion/extractor.py` (line ~100)
- `src/orchestrator/supervisor.py` (line ~150)

The expected endpoint is `POST /generate` with:
```json
{
  "prompt": "...",
  "sampling_params": {...},
  "regex": "..."
}
```

