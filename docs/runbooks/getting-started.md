# Getting Started Guide

This guide will help you set up and run Project Vyasa on your development machine or NVIDIA DGX system.

## Prerequisites

- **Docker** and **Docker Compose** installed
- **NVIDIA GPU** with CUDA support (for Cortex, Drafter, and Embedder services)
- **Git** for cloning the repository
- **8GB+ RAM** recommended
- **50GB+ disk space** for models and data
- **Project Created via Console**: You must create a project before processing documents (Project-First workflow)

## Step 1: Clone and Navigate

```bash
git clone <repository-url>
cd project-vyasa
```

## Step 2: Configure Environment

Create your environment configuration file:

```bash
cd deploy
cp .env.example .env
```

The `.env.example` file contains all necessary configuration variables. Edit `.env` if you need to customize:

- **Model paths**: Change `BRAIN_MODEL_PATH`, `WORKER_MODEL_PATH`, `VISION_MODEL_PATH` if using different models
- **Ports**: Adjust port mappings if defaults conflict with existing services
- **Database name**: Modify `GRAPH_DB_NAME` if needed
- **Security**: Set `ARANGO_ROOT_PASSWORD`, `QDRANT_API_KEY`, `CONSOLE_PASSWORD`, `NEXTAUTH_SECRET`

**Important**: If you change model paths, the models will be re-downloaded on first container start (this can take time).

## Step 3: Start Services

From the `deploy/` directory, start all services:

```bash
./start.sh
```

Or manually:

```bash
docker-compose up -d
```

**Note**: The `start.sh` script will:
1. Start all services via Docker Compose
2. Wait for ArangoDB to become healthy
3. Seed initial roles (if seed script exists)
4. Poll the orchestrator health endpoint (`/health`)
5. Print "✅ System Online: http://localhost:3000" when ready

If the orchestrator fails to respond within 60 seconds, the script will print a warning and exit. Check logs with `docker logs vyasa-orchestrator`.

**First Run**: The first time you start the services, Docker will:
1. Pull required images (this may take several minutes)
2. Download ML models on first use:
   - **Brain**: `Llama-3.3-70B` (~140GB)
   - **Worker**: `Qwen 2.5 49B` (~98GB)
   - **Vision**: `Qwen2-VL-72B` (~144GB)
   - **Embedder**: `all-MiniLM-L6-v2` (~90MB)
3. Initialize databases (ArangoDB and Qdrant)
4. Seed initial roles (if running seed script)

**Expected Output**: You should see all 9 services starting:
- ✅ `cortex-brain` (Brain - SGLang, Port 30000)
- ✅ `cortex-worker` (Worker - SGLang, Port 30001)
- ✅ `cortex-vision` (Vision - SGLang, Port 30002)
- ✅ `drafter` (Drafter - Ollama, Port 11434)
- ✅ `memory` (Memory - ArangoDB, Port 8529)
- ✅ `console` (Console - Next.js, Port 3000)
- ✅ `embedder` (Embedder - Sentence Transformers, Port 80)
- ✅ `vector` (Vector - Qdrant, Port 6333)
- ✅ `orchestrator` (Orchestrator - Python, Port 8000)

## Step 4: Verify Services

Check that all containers are running:

```bash
docker-compose ps
```

All services should show `Up` status. If any service is failing, check logs:

```bash
docker-compose logs <service-name>
# Example: docker-compose logs cortex-brain
```

## Step 5: Access the Console

Open your browser and navigate to:

**http://localhost:3000**

You should see the Project Vyasa Console dashboard. Log in with your `CONSOLE_PASSWORD` (set in `.env`).

## Step 6: Create a Project (Required)

**Project Vyasa uses a Project-First workflow.** All document processing requires a project context.

### 6.1 Navigate to Projects

1. Click **"Projects"** in the navigation or go to `/projects`
2. You should see the Projects home page with a table of existing projects (empty on first run)

### 6.2 Create New Project

1. Click **"New Project"** button
2. Fill in the form:
   - **Title** (required): e.g., "Security Analysis of Web Applications"
   - **Thesis** (required): The core argument or hypothesis
   - **Research Questions** (required): One question per line
   - **Anti-Scope** (optional): Explicitly out-of-scope topics
   - **Target Journal** (optional): e.g., "IEEE Security & Privacy"
3. Click **"Create Project"**
4. You will be redirected to the project workbench (`/projects/[id]`)

**Success**: You now have a project with a unique `project_id`. This ID will be used for all document processing.

## Step 7: Upload Seed Corpus

### 7.1 Navigate to Project Workbench

If you just created a project, you're already on the workbench. Otherwise, click on a project in the projects table.

### 7.2 Upload Files

1. In the **"Seed Corpus"** panel (left column), use the file uploader
2. Drag and drop a PDF file, or click to browse
3. Supported formats: `.pdf`, `.md`, `.txt`, `.json`
4. The file will be uploaded to `/api/proxy/orchestrator/ingest/pdf` with `project_id` automatically included

**Expected**: The file should appear in the "Files" list below the uploader.

## Step 8: Process Documents

### 8.1 Trigger Processing

1. After uploading a file, the system will automatically process it (or you can trigger processing manually)
2. The processing workflow will:
   - Extract text from the PDF
   - Inject project context (Thesis, RQs) into the extraction pipeline
   - Send to Worker (Cartographer) for knowledge graph extraction
   - Tag claims as HIGH/LOW priority based on Research Questions
   - Validate with Critic node
   - Filter by confidence with Vision node
   - Store triples in ArangoDB (linked to `project_id`)

**Expected**: You should see a progress indicator, then a success message.

### 8.2 View Extraction Results

1. Navigate to the **"Processing"** panel (center column)
2. You should see extraction results and graph visualization
3. Nodes and edges are project-scoped (only shows data for the current project)

**Success**: If you see nodes and edges, the extraction pipeline is working! 🎉

## Step 9: Test Search

1. Use the search bar in the Console (if available)
2. Enter a query related to your document (e.g., "security vulnerability")
3. You should see relevant document chunks returned (project-scoped)

**Success**: If search returns results, the vector search pipeline is working! 🎉

## Troubleshooting

### Services Won't Start

**Check GPU availability:**
```bash
nvidia-smi
```

**Check Docker GPU runtime:**
```bash
docker run --rm --gpus all nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi
```

### Cortex Services Fail (Brain/Worker/Vision)

**Check logs:**
```bash
docker-compose logs cortex-brain
docker-compose logs cortex-worker
docker-compose logs cortex-vision
```

**Common issues:**
- Model download failed: Check internet connection and disk space
- GPU not available: Verify `nvidia-smi` works and GPU IDs are correct in `.env`
- Port conflict: Change `PORT_BRAIN`, `PORT_WORKER`, or `PORT_VISION` in `.env`
- GPU reservation conflict: Ensure GPU IDs don't overlap between services

### Console Shows Connection Errors

**Verify service URLs:**
- Check that `ORCHESTRATOR_URL`, `MEMORY_SERVICE_URL`, etc. are correct in `.env`
- Ensure all services are running: `docker-compose ps`

### Database Initialization Fails

**Reset databases (⚠️ deletes all data):**
```bash
docker-compose down -v
docker-compose up -d
```

### Document Upload Fails with "No active project selected"

**Solution**: You must create a project first. Navigate to `/projects` and click "New Project".

### Extraction Returns Empty Graph

**Check**:
- Project context is being injected (check logs for "Hydrated project context")
- Research Questions are defined in the project
- Document contains relevant content matching the Thesis/RQs

## Next Steps

Once the smoke test passes:

1. **Read the Architecture Docs**: Understand how services interact
   - [System Map](../architecture/system-map.md)
   - [Agent Workflow](../architecture/agent-workflow.md)

2. **Explore the Codebase**:
   - `src/console/` - Next.js frontend
   - `src/orchestrator/` - LangGraph workflows
   - `src/ingestion/` - Knowledge extraction logic
   - `src/project/` - Project Kernel (ProjectConfig, ProjectService)
   - `src/shared/` - Shared schemas and config

3. **Review Decisions**: Understand why we made certain choices
   - [ADR 001: Local Vector DB](../decisions/001-local-vector-db.md)

## Development Workflow

### Making Changes

1. **Frontend changes**: Edit files in `src/console/`
   - Changes hot-reload in development mode
   - Rebuild: `docker-compose build console`

2. **Backend changes**: Edit files in `src/orchestrator/`, `src/ingestion/`
   - Changes require container restart: `docker-compose restart orchestrator`

3. **Configuration changes**: Edit `deploy/.env`
   - Restart affected services: `docker-compose restart <service>`

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f cortex-brain

# Last 100 lines
docker-compose logs --tail=100 console
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes data)
docker-compose down -v
```

## Service Health Checks

### Manual Health Checks

```bash
# Brain
curl http://localhost:30000/health

# Worker
curl http://localhost:30001/health

# Vision
curl http://localhost:30002/health

# Orchestrator
curl http://localhost:8000/health

# Qdrant
curl http://localhost:6333/health

# ArangoDB
curl http://localhost:8529/_api/version
```

### Console Health

The Console UI includes a health status indicator. Check the settings panel for service connectivity.

## Common Commands Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart cortex-brain

# Rebuild a service
docker-compose build console

# Check service status
docker-compose ps

# Execute command in container
docker-compose exec orchestrator bash
```

## Getting Help

- **Documentation**: See [docs/README.md](../README.md) for full documentation index
- **Architecture**: Review [System Map](../architecture/system-map.md) for data flows
- **Issues**: Check service logs first: `docker-compose logs <service>`

## Success Criteria

You've successfully set up Project Vyasa when:

✅ All 9 services are running (`docker-compose ps`)  
✅ Console is accessible at http://localhost:3000  
✅ You can create a project via the Console  
✅ You can upload files to a project's seed corpus  
✅ Document processing extracts knowledge graph (nodes and edges)  
✅ Knowledge graph visualization shows project-scoped data  
✅ Search functionality returns relevant results  
✅ Async job system works (submit job, poll status)  

Welcome to Project Vyasa! 🚀
