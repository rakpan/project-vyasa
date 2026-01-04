# Project Vyasa — The AI Research Factory

**A local-first framework for executing evidence-bound research workflows.**

---

## Executive Summary

Vyasa is a **research workspace** optimized for NVIDIA DGX Spark. It helps researchers turn unstructured documents into rigorously sourced, evidence-backed manuscripts that can stand up to peer review. 

Vyasa is not a chatbot. It is a platform for building and governing research artifacts.

### Quick links
- Architecture & system map: `docs/architecture/system-map.md`
- Orchestrator runtime/bridge: `docs/architecture/orchestrator-architecture-ops.md` and `docs/orchestrator-guide.md`
- UX standards: `docs/ux-standards.md` (checklist) and `docs/ux-guide.md` (examples)
- Config/env flags: `docs/configuration/config-reference.md`
- Deployment: `docs/deployment.md` — Service setup and optional components
- Testing: `docs/guides/testing.md`
- Refactors/migrations: `docs/refactors/` and `docs/migrations/`

## What Vyasa does

Vyasa helps you:

- Collect source documents into a single project (papers, PDFs, reports, notes).
- Extract claims, facts, and relationships from those sources.
- Track exactly where each claim came from.
- Highlight conflicts, gaps, and uncertainty instead of hiding them.
- Assemble manuscripts from small, evidence-bound blocks instead of raw text.

If a claim is not tied to evidence in the graph, it does not belong in the final manuscript.

---

## How it works (simple view)

Every Vyasa project follows the same method:

1. Define your thesis and research questions.
2. Ingest and normalize your sources into the project.
3. Let models propose candidate claims and links between them.
4. Review conflicts, gaps, and weak evidence as a human decision-maker.
5. Build manuscript sections from blocks that each carry claim IDs and citations.

The models help you see and structure the evidence. You remain in charge of what is true and what is publishable.

---

## The core idea: graph-backed research

Under the hood, Vyasa treats your research as a graph:

- Nodes represent claims, sources, entities, methods, and assumptions.
- Edges capture relationships like “supports,” “contradicts,” “derived from,” or “uses method.”
- Every model interaction writes to this graph under a specific project.

ArangoDB is the system of record. If a step is not in the graph, it did not occur.

This gives you:

- A complete audit trail from manuscript paragraph → claim → source.
- Versioned evolution of your thinking over time.
- A machine-readable structure that other tools can inspect, validate, or export.

---

## Why this matters

Most AI tools give you fluent answers with weak or invisible evidence. This is not acceptable for high-stakes work.

Vyasa takes the opposite approach:

- Evidence first, prose second.
- Conflicts and uncertainty are surfaced, not smoothed over.
- Manuscripts are compiled from governed blocks, not ad-hoc generations.

The result is a workflow where AI accelerates the grunt work of extraction and organization, while humans maintain control over judgment and truth.

---

## Architecture & Design (read more)
- System map, kernels, and committee: `docs/architecture/system-map.md`
- Ports/services and resource optimization: `docs/architecture/04-resource-optimization.md`
- Observability/Opik: `docs/architecture/05-telemetry-and-observability.md`
- Node module organization: `docs/architecture/module-map.md`
- Web Augmentation (optional): `docs/decisions/ADR-004-web-augmentation-sidecar.md` — Trigger-driven web augmentation via Firecrawl sidecar

### Web Augmentation Loop (Optional)

When enabled (`WEB_AUGMENTATION_ENABLED=true`), Vyasa can augment local knowledge with web sources:

```
┌─────────────────────────────────────────────────────────────┐
│                    Vyasa Core (Orchestrator)                │
│                                                             │
│  DisputeContext → Discovery → Normalization → Intelligence │
│       ↓              ↓            ↓              ↓          │
│   Trigger      Search URLs   Normalize      Extract Claims │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ HTTP only (no SDK imports)
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Firecrawl Sidecar (CPU-only)                   │
│                                                             │
│                    Retrieval: Scrape URLs                   │
│                    Returns: Markdown content               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Markdown
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    Vyasa Core (Governance)                  │
│                                                             │
│              ReviewTask(PENDING) → Human Approval          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Boundaries:**
- **Vyasa Core decides** (when/what to augment)
- **Firecrawl retrieves** (HTTP-only, no SDK imports)
- **GPUs reserved** for worker/brain inference (Firecrawl CPU-only)
- **Feature flag** controls enablement (disabled by default)

## Operations & Maintenance
- **Backups**: `docs/runbooks/backups.md` - Daily automated backups (ArangoDB + Qdrant) with restore procedures and weekly off-host sync
- DGX runtime: `deploy/runbooks/dgx-runtime.md` - Resource management and monitoring

---

## The Name: Veda Vyasa

The project is named after the legendary sage **Veda Vyasa**, whose name literally means *Compiler* or *Arranger* in Sanskrit.

**The Original Information Architect**  Vyasa is credited with taking a single, primordial body of knowledge and classifying it into distinct branches to make it usable at scale.

**The Chronicler**  By compiling the *Mahabharata* and the *Puranas*, Vyasa bridged abstract philosophy with human narrative. Project Vyasa bridges raw documents with evidence-bound research manuscripts.

**Philosophy of Arrangement**  Vyasa did not invent knowledge—he structured it. Likewise, this system does not invent facts. **It arranges evidence.**

---

## Quick Start

### Prerequisites

- **NVIDIA DGX Spark (Grace Blackwell)** or compatible system with:
  - Docker and Docker Compose
  - NVIDIA Container Toolkit configured
  - At least 128GB unified memory (120GB+ required, 24GB headroom recommended)
  - Multiple GPUs for inference services

### Step-by-Step Setup

#### Step 1: Preflight Check

Validate your environment before starting:

```bash
./scripts/preflight_check.sh
```

This checks:
- ✅ NVIDIA Grace Blackwell superchip detection
- ✅ Unified memory (120GB+ required)
- ✅ Knowledge Harvester dataset directory (`/raid/datasets/`)
- ✅ Port availability (30000, 30001, 30002, 11435, ${PORT_EMBEDDER:-8000}, 8529, 6333, 8000, 3000)
- ✅ Expertise configuration file (optional)

**If checks fail**: Resolve issues before proceeding.

#### Step 2: Configure Environment

```bash
cd deploy
cp .env.example .env
# Edit .env with your settings
```

**Required settings:**
- `ARANGO_ROOT_PASSWORD` - ArangoDB root password
- `QDRANT_API_KEY` - Qdrant API key
- `CONSOLE_PASSWORD` - Console login password
- `HF_TOKEN` - HuggingFace Hub token (get from https://huggingface.co/settings/tokens)
- `BRAIN_MODEL_PATH`, `WORKER_MODEL_PATH`, `VISION_MODEL_PATH` - Model paths (HuggingFace or local)
- `BRAIN_GPU_IDS`, `WORKER_GPU_IDS`, `VISION_GPU_IDS` - GPU assignments

**Optional (Opik observability tracing):**
- `OPIK_ENABLED` - set to `true` to enable (default `false`)
- `OPIK_BASE_URL` - Opik instance URL
- `OPIK_API_KEY` - API key if required
- `OPIK_PROJECT_NAME` - trace project tag (default `vyasa`)
- `OPIK_TIMEOUT_SECONDS` - timeout for Opik calls (default `2`)

#### Step 3: Start the System

```bash
./scripts/run_stack.sh start
# Optional: ./scripts/run_stack.sh start --opik
```

Helpful commands:
- Stop services: `./scripts/run_stack.sh stop [--opik]`
- Tail logs: `./scripts/run_stack.sh logs [--opik] [service]`

#### Step 4: Verify System Status

```bash
cd deploy
docker compose ps
```

All services should show `Up` status. Check logs if any service fails:

```bash
docker compose logs <service-name>
```

#### Step 5: Access the Console

Open your browser: **http://localhost:3000**

Log in with your `CONSOLE_PASSWORD` (set in `deploy/.env`).

**Navigation Basics:**
- `/` redirects to `/projects` (canonical entry)
- From **Projects**, open a project to see recent jobs and "Resume" links
- Recent jobs deep-link to the Research Workbench with `jobId`, `projectId`, and optional `pdfUrl`
- **Research Workbench** layout:
  - 3-panel (document + graph + workbench) when `pdfUrl` provided
  - 2-panel (graph + workbench) when absent
  - Redirects if required params missing

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
2. The system automatically:
   - Extracts knowledge graph (entities, relations)
   - Tags claims as HIGH/LOW priority based on Research Questions
   - Validates evidence binding
   - Stores in ArangoDB

#### Step 8: Stop the System

```bash
./scripts/run_stack.sh stop
```

Or manually:

```bash
cd deploy
docker compose down
```

---

## Scripts & Operations

| Script | Purpose |
|--------|---------|
| `scripts/init_vyasa.sh --bootstrap-secrets` | Generate secure credentials in `.secrets.env` |
| `scripts/preflight_check.sh` | Validate hardware, memory, ports, Python imports |
| `scripts/deploy_verify.sh` | End-to-end integration test (Go/No-Go gate) |
| `scripts/run_stack.sh start\|stop\|logs [--opik]` | **Default**: Start/stop/monitor all services (add `--opik` for observability) |
| `scripts/vyasa-cli.sh` | Operational utilities (merge nodes, etc.) |
| `scripts/run_tests.sh` | Run pytest test suite |
| `scripts/run_mock_llm.sh` | Start mock LLM server for testing |

**When to use which:**
- **Default (start/stop)**: `run_stack.sh start|stop [--opik]`
- **Before first startup**: `preflight_check.sh`, then `init_vyasa.sh --bootstrap-secrets`
- **Testing/development**: `run_tests.sh`, `run_mock_llm.sh`
- **Operational tasks**: `vyasa-cli.sh merge ...`

---

## DGX Spark Optimization (Grace Blackwell)

Project Vyasa is optimized for DGX-class systems with unified memory:

- **FP4/MXFP4 Inference**: Cortex Brain/Worker use reduced precision with `--mem-fraction-static` to fit within unified memory
- **CPU Pinning**: ArangoDB/Orchestrator pinned to efficiency cores; inference services pinned to performance cores
- **KV Cache Guardrail**: `MAX_KV_CACHE_GB` limits unified memory pressure during concurrent model inference
- **Model Configuration**: Tune model paths and GPU assignments via `deploy/.env`

---

## Project Structure

```
project-vyasa/
├── src/
│   ├── console/          # Next.js frontend (UI, auth, navigation)
│   ├── orchestrator/     # LangGraph state machine (workflow coordinator)
│   ├── ingestion/        # Knowledge extraction (claims, entities, relations)
│   ├── embedder/         # Sentence-Transformers embedding service
│   ├── shared/           # Pydantic schemas, utilities, constants
│   ├── project/          # Project kernel (ProjectConfig, service)
│   ├── manuscript/       # Manuscript kernel (blocks, patches)
│   └── tests/            # Test suite (pytest)
├── deploy/
│   ├── docker-compose.yml
│   ├── docker-compose.opik.yml
│   ├── .env.example
│   └── scripts/          # Init helpers (ArangoDB, Qdrant)
├── scripts/
│   ├── preflight_check.sh
│   ├── run_stack.sh
│   ├── vyasa-cli.sh
│   ├── run_tests.sh
│   └── run_mock_llm.sh
└── docs/
    ├── architecture/     # System design (C4, workflow, model inventory)
    ├── runbooks/        # Operational runbooks (operator handbook)
    ├── guides/          # Developer guides (onboarding, testing)
    ├── decisions/        # Architecture Decision Records
    ├── configuration/    # Configuration guides (rigor levels)
    └── migrations/       # Migration guides (React Flow, etc.)
```

---

## Documentation & Resources

- **[Quick Start Guide](QUICK_START.md)** - Fastest path to running Project Vyasa (5 minutes)
- **[Operator Handbook](docs/runbooks/operator-handbook.md)** - Detailed step-by-step setup
- **[System Architecture](docs/architecture/system-map.md)** - C4 Container Diagram
- **[Console Navigation](docs/runbooks/console-navigation.md)** - Projects → Jobs → Workbench flow
- **[Agent Workflow](docs/architecture/agent-workflow.md)** - LangGraph State Machine
- **[Developer Onboarding](docs/guides/developer-onboarding.md)** - Coding standards (Strict JSON, Pydantic-first)
- **[Architecture Overview](docs/architecture/00-overview.md)** - Full architecture docs

---

## Key Features

✅ **Evidence-First Design**  
Claims bind to sources before writing begins; no orphaned assertions.

✅ **Local-First Processing**  
All inference happens on your DGX; no external APIs, no data leakage.

✅ **Governed Workflows**  
System prompts versioned in ArangoDB; change behavior without redeployment.

✅ **Strict Schema Compliance**  
SGLang regex constraints ensure JSON extraction always matches contract.

✅ **Production-Ready**  
Structured logging, error handling, graceful degradation, NextAuth authentication.

✅ **Dynamic Role System**  
Orchestrator manages prompts; no hardcoded agent behaviors.

✅ **Research-Grade Provenance**  
Full citation tracking, conflict surfacing, uncertainty preservation.

---

## License

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3** (or later).

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

---

## Contributing

We welcome contributions that align with the "Research Factory" philosophy:
- Strict JSON extraction (no "prompt and pray")
- Pydantic-first schema design
- Evidence-binding before text generation
- Governance-by-design, not bolted-on

See the **Development Guide** for coding standards and contribution workflow.
