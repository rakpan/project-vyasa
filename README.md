# Project Vyasa — The AI Research Factory

> **A local-first framework for executing evidence-bound research workflows.**

Project Vyasa is a local-first **research execution framework** that operationalizes how evidence is extracted, validated, governed, and composed into research artifacts.

Rather than generating free-form text, Vyasa enforces a factory model where:
- claims must bind to evidence,
- citations must resolve,
- manuscripts are assembled from governed blocks,
- and humans remain the final authority.

Vyasa is optimized for DGX-class systems to support multi-model reasoning and high-throughput local inference. It is fundamentally a **discipline for research**, not a chat interface and not an ETL pipeline.

## The Name

The project is named after the legendary sage **Veda Vyasa**, whose name literally means *Compiler* or *Arranger* in Sanskrit.

- **The Original Information Architect**  
   Vyasa is credited with taking a single, primordial body of knowledge and classifying it into distinct branches to make it usable at scale.

- **The Chronicler**  
   By compiling the *Mahabharata* and the *Puranas*, Vyasa bridged abstract philosophy with human narrative. Project Vyasa bridges raw documents with evidence-bound research manuscripts.

- **Philosophy of Arrangement**  
   Vyasa did not invent knowledge — he structured it.  Likewise, this system does not invent facts. It **arranges evidence**.

The knowledge graph is the system of record.  If it is not persisted, it did not happen.

## The Why

Modern research workflows fail in predictable ways:

- Evidence is extracted implicitly or manually.
- AI tools generate fluent text without enforceable provenance.
- Citations drift, logic gaps go unnoticed, and validation happens late.
- Reproducibility depends on human memory rather than systems.

Project Vyasa addresses this by treating research as an **engineered pipeline**, not a writing task.All running **locally**, optimized for DGX Spark. No data leakage.

## Architecture Docs
- Quickstart and diagrams: [docs/architecture/00-overview.md](docs/architecture/00-overview.md)
- Full set: [docs/architecture](docs/architecture)

## Native Vision (Core Philosophy)

- **Factory, Not Chatbot**: We build artifacts (Graphs, Manuscripts), not conversations.
- **Project-First**: Every action is downstream of a `project_id` (Thesis + RQs + Anti-Scope injected into prompts).
- **Graph = System of Record**: If it is not persisted to ArangoDB, it did not happen.
- **Governed Outputs**: Orchestrator guarantees schema contracts; no silent failures on DB writes.
- **Block-Based**: Manuscripts are bound blocks (Text + ClaimIDs + CitationKeys), never raw strings.

## The Four Kernels (Domains)

- **Project Kernel (Intent)**: `ProjectConfig` (Thesis, RQs, Anti-Scope, Target Journal). No agent runs without it.
- **Knowledge Kernel (Evidence)**: Ingestion + extraction of claims, tagging priority HIGH/LOW by project RQs; high recall, tag then rank.
- **Manuscript Kernel (Production)**: Blocks and Patches; every block must bind to specific Claim IDs and Citation Keys. Humans accept/reject (redline review).
- **Governance Kernel (Quality)**: Guards for drift, citation, evidence, contract. Roles/prompts are versioned in DB, not hardcoded.

## Architecture Overview

Project Vyasa follows a **Committee of Experts Architecture** with functional naming:

- **Brain** (Port 30000): High-level reasoning and routing decisions (SGLang, large model)
- **Worker** (Port 30001): Strict JSON extraction and validation (SGLang, cheap model)
- **Vision** (Port 30002): Confidence scoring and filtering (SGLang, large model)
- **Drafter** (Port 11434): The Writer. Ollama for prose generation and summarization
- **Graph** (Port 8529): The Memory. ArangoDB knowledge graph storage
- **Vector** (Port 6333): The Search Index. Qdrant for semantic embeddings
- **Embedder** (Port 8000): The Vectorizer. Sentence-Transformers for text-to-vector conversion
- **Console** (Port 3000): The Face. Next.js UI with NextAuth authentication
- **Orchestrator** (Port 8000): The Coordinator. LangGraph state machine managing the workflow

## Quick Start

### Prerequisites

- **NVIDIA DGX Spark (GB10)** or compatible system with:
  - Docker and Docker Compose
  - NVIDIA Container Toolkit configured
  - At least 128GB unified memory (for DGX Spark)
  - Multiple GPUs for Cortex services

### Step-by-Step Setup

#### Step 1: Preflight Check

Before starting, validate your environment:

```bash
./scripts/preflight_check.sh
```

This checks:
- ✅ NVIDIA GB10 superchip detection
- ✅ Unified memory (120GB+ required, 24GB headroom recommended)
- ✅ Knowledge Harvester dataset directory (`/raid/datasets/`)
- ✅ Port availability (30000, 30001, 8529)
- ✅ Expertise configuration file (optional)

**If checks fail**: Resolve issues before proceeding.

#### Step 2: Configure Environment

```bash
cd deploy
cp .env.example .env
# Edit .env with your model paths, GPU IDs, and secrets
```

**Required settings**:
- `ARANGO_ROOT_PASSWORD` - ArangoDB root password
- `QDRANT_API_KEY` - Qdrant API key
- `CONSOLE_PASSWORD` - Console login password
- `HF_TOKEN` - HuggingFace Hub access token (required for model downloads; get from https://huggingface.co/settings/tokens)
- `BRAIN_MODEL_PATH`, `WORKER_MODEL_PATH`, `VISION_MODEL_PATH` - Model paths (HuggingFace Hub paths like `meta-llama/Llama-3.3-70B-Instruct` or local filesystem paths)
- `BRAIN_GPU_IDS`, `WORKER_GPU_IDS`, `VISION_GPU_IDS` - GPU assignments

**Optional (Opik observe-only tracing)**:
- `OPIK_ENABLED` - set to `true` to enable Opik tracing (default `false`)
- `OPIK_BASE_URL` - base URL of your Opik instance
- `OPIK_API_KEY` - API key if required
- `OPIK_PROJECT_NAME` - project tag for traces (default `vyasa`)
- `OPIK_TIMEOUT_SECONDS` - timeout for Opik calls (default `2`)

#### Step 3: Start the System

Use the unified stack runner (add `--opik` to include Opik services):

```bash
./scripts/run_stack.sh start
# optional: ./scripts/run_stack.sh start --opik
```

Helpful commands:
- Stop services: `./scripts/run_stack.sh stop [--opik]`
- Tail logs: `./scripts/run_stack.sh logs [--opik] [service]`

#### Step 4: Verify System Status

Check all services are running:

```bash
cd deploy
docker compose ps
```

All services should show `Up` status. Check logs if any service fails:

```bash
docker compose logs <service-name>
# Example: docker compose logs cortex-worker
```

#### Step 5: Access the Console

Open your browser:

**http://localhost:3000**

Log in with your `CONSOLE_PASSWORD` (set in `deploy/.env`).

**Navigation basics**
- Root `/` redirects to `/projects` (canonical entry).
- From **Projects**, open a project to see recent jobs and “Resume” links; a recent job will deep-link to the Research Workbench with `jobId`/`projectId`/`pdfUrl` populated.
- **Research Workbench** requires `jobId` and `projectId`; `pdfUrl` is optional (3-panel layout when present, 2-panel when absent). If required params are missing, you’ll be redirected back to Projects with a toast.

#### Step 6: Create Your First Project

1. Navigate to **Projects** → **New Project**
2. Fill in:
   - **Title**: e.g., "Security Analysis of Web Applications"
   - **Thesis**: Your core research argument
   - **Research Questions**: One per line
   - **Anti-Scope**: Topics to exclude (optional)
3. Click **Create Project**

#### Step 7: Upload and Process Documents

1. In the project workbench, upload a PDF to the **Seed Corpus**
2. The system will automatically process it:
   - Extract knowledge graph (entities, relations)
   - Tag claims as HIGH/LOW priority based on Research Questions
   - Validate evidence binding
   - Store in ArangoDB

### Stopping the System

```bash
cd deploy
./stop.sh
```

Or manually:

```bash
cd deploy
docker compose down
```

### Script Reference

| Script | Location | Purpose |
|--------|----------|---------|
| **Preflight Check** | `scripts/preflight_check.sh` | Validates hardware, memory, ports before startup |
| **Start/Stop** | `scripts/run_stack.sh` | Unified start/stop/logs (add `--opik` to include Opik services) |
| **Console Navigation** | `docs/runbooks/console-navigation.md` | Describes Projects → Job → Workbench flow, guards, and layout rules |
| **Operational CLI** | `scripts/vyasa-cli.sh` | Operational utilities (merge nodes, etc.) |
| **Test Runner** | `scripts/run_tests.sh` | Run pytest test suite |
| **Mock LLM** | `scripts/run_mock_llm.sh` | Start mock LLM server for testing |

**When to use which script**:
- **Start/Stop (default)**: `run_stack.sh start|stop [--opik]`
- **Preflight**: `preflight_check.sh`
- **Development/testing**: `scripts/run_tests.sh`, `scripts/run_mock_llm.sh`
- **Operations**: `scripts/vyasa-cli.sh merge ...`

## Service Ports

| Service | Port | GPU IDs | Purpose |
|---------|------|---------|---------|
| Console | 3000 | N/A | Web UI (Next.js) |
| Brain | 30000 | `${BRAIN_GPU_IDS}` | High-level reasoning (SGLang) |
| Worker | 30001 | `${WORKER_GPU_IDS}` | JSON extraction/validation (SGLang) |
| Vision | 30002 | `${VISION_GPU_IDS}` | Confidence scoring (SGLang) |
| Drafter | 11434 | `${DRAFTER_GPU_IDS}` | Ollama Chat API |
| Graph | 8529 | N/A | ArangoDB Web UI & API |
| Vector | 6333 | N/A | Qdrant API |
| Embedder | 80 | N/A | Embedding Service API |
| Orchestrator | 8000 | N/A | LangGraph API |

**Note**: All ports and GPU IDs are configurable via `deploy/.env` file.

## DGX Spark Optimization (Grace Blackwell)

- **FP4/MXFP4 Inference**: Cortex Brain/Worker use FP4/MXFP4 with `--mem-fraction-static` to fit unified memory; tune model paths via `deploy/.env`.
- **CPU Pinning**: Compose pins ArangoDB/Orchestrator to efficiency cores and inference services to performance cores (`cpuset` in `deploy/docker-compose.yml`).
- **KV Cache Guardrail**: `MAX_KV_CACHE_GB` (config) limits unified memory pressure when running concurrent model servers.

## Documentation

- **[Quick Start Guide](QUICK_START.md)**: Fastest path to running Project Vyasa (5-minute setup)
- **[Getting Started Guide](docs/runbooks/getting-started.md)**: Detailed step-by-step setup instructions
- **[System Architecture](docs/architecture/system-map.md)**: C4 Container Diagram
- **[Agent Workflow](docs/architecture/agent-workflow.md)**: LangGraph State Machine
- **[Development Guide](docs/guides/development.md)**: Coding standards and conventions

## Key Features

- **Dynamic Role System**: System prompts stored in ArangoDB, editable without redeployment
- **Strict JSON Extraction**: SGLang regex constraints ensure schema compliance
- **Local-First**: All processing happens on your DGX, no external APIs
- **Secure by Default**: NextAuth authentication, password-protected databases
- **Production-Ready**: Structured logging, error handling, graceful degradation

## Project Structure

```
project-vyasa/
├── src/                    # Source code
│   ├── console/            # Next.js frontend
│   ├── orchestrator/       # LangGraph supervisor
│   ├── ingestion/          # Knowledge extractor
│   ├── embedder/           # Sentence-Transformers service
│   └── shared/             # Shared schemas and utilities
├── deploy/                  # Deployment configuration
│   ├── docker-compose.yml   # Service definitions
│   ├── .env.example         # Environment template
│   ├── start.sh             # Legacy quick start script
│   ├── stop.sh              # Legacy shutdown script
│   └── scripts/             # Initialization helpers
├── scripts/                 # Operational scripts
│   ├── preflight_check.sh   # Pre-startup validation
│   ├── run_stack.sh         # Unified start/stop/logs (with optional Opik)
│   ├── vyasa-cli.sh         # Operational CLI (merge, etc.)
│   ├── run_tests.sh         # Test runner
│   └── run_mock_llm.sh      # Mock LLM for testing
└── docs/                    # Documentation
    ├── architecture/        # System design docs
    ├── decisions/           # Architecture Decision Records
    └── runbooks/            # Operational guides
```

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

## Contributing

We welcome contributions that align with the "Research Factory" philosophy. See the Development Guide for coding standards (Strict JSON, Pydantic-first, no "prompt and pray").
