# Project Vyasa: The AI Research Factory

> **A local-first, DGX-powered knowledge graph engine for research automation.**

Project Vyasa is not just a script—it's a complete research factory that transforms unstructured documents into structured knowledge graphs. Built on NVIDIA DGX infrastructure, it combines SGLang inference, LangGraph orchestration, and graph databases to create a self-contained, privacy-preserving research automation system.

## The Why

Traditional research workflows require manual extraction, validation, and synthesis of information from papers, reports, and documents. Project Vyasa automates this process:

- **Extract**: Transform unstructured text into structured entities and relations
- **Validate**: Identify logic gaps, missing evidence, and contradictions
- **Synthesize**: Generate summaries and insights from the knowledge graph
- **Query**: Semantic search across your research corpus

All running **locally** on your DGX—no cloud dependencies, no data leakage.

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

- NVIDIA DGX with Docker and Docker Compose
- NVIDIA Container Toolkit configured
- At least 2 GPUs (one for Cortex, one for Drafter)

### Setup

1. **Configure Environment**

   ```bash
   cp deploy/.env.example deploy/.env
   # Edit deploy/.env with your configuration
   ```

2. **Launch Services**

   ```bash
   cd deploy
   docker compose up -d
   ```

3. **Seed Initial Roles (idempotent)**

   ```bash
   # If start.sh didn’t already seed:
   docker compose exec orchestrator python -m src.scripts.seed_roles
   ```

4. **Access Console**

   Open `http://localhost:3000` and log in with your `CONSOLE_PASSWORD`.

### Smoke Test

1. Upload a PDF document through the Console
2. Verify extraction creates nodes and edges in the graph
3. Query the graph to confirm data persistence

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

- **[System Architecture](docs/architecture/system-map.md)**: C4 Container Diagram
- **[Agent Workflow](docs/architecture/agent-workflow.md)**: LangGraph State Machine
- **[Development Guide](docs/guides/development.md)**: Coding standards and conventions
- **[Getting Started](docs/runbooks/getting-started.md)**: Detailed setup instructions

## Key Features

- **Dynamic Role System**: System prompts stored in ArangoDB, editable without redeployment
- **Strict JSON Extraction**: SGLang regex constraints ensure schema compliance
- **Local-First**: All processing happens on your DGX, no external APIs
- **Secure by Default**: NextAuth authentication, password-protected databases
- **Production-Ready**: Structured logging, error handling, graceful degradation

## Project Structure

```
project-vyasa/
├── src/
│   ├── console/          # Next.js frontend
│   ├── orchestrator/     # LangGraph supervisor
│   ├── ingestion/        # Knowledge extractor
│   ├── embedder/         # Sentence-Transformers service
│   └── shared/           # Shared schemas and utilities
├── deploy/
│   ├── docker-compose.yml
│   ├── .env.example
│   └── scripts/          # Initialization scripts
└── docs/
    ├── architecture/    # System design docs
    ├── decisions/        # Architecture Decision Records
    └── runbooks/         # Operational guides
```

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

## Contributing

We welcome contributions that align with the "Research Factory" philosophy. See the Development Guide for coding standards (Strict JSON, Pydantic-first, no "prompt and pray").
