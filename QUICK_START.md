# Quick Start Guide - Project Vyasa

> **The fastest path to running Project Vyasa on DGX Spark (GB10)**

## TL;DR

```bash
# 1. Preflight check
./scripts/preflight_check.sh

# 2. Configure environment
cd deploy && cp .env.example .env && # edit .env

# 3. Start system (first time)
./scripts/run_stack.sh start  # add --opik to include Opik services

# 4. Access console
open http://localhost:3000
```

## Detailed Steps

### 1. Preflight Check (2 minutes)

Validates your DGX Spark environment:

```bash
./scripts/preflight_check.sh
```

**Must pass**: GPU detection, memory (120GB+), ports available.

### 2. Configure Environment (5 minutes)

```bash
cd deploy
cp .env.example .env
# Edit .env with your:
# - Model paths
# - GPU IDs
# - Passwords (ARANGO_ROOT_PASSWORD, QDRANT_API_KEY, CONSOLE_PASSWORD)
```

### 3. Start System (10-30 minutes first time)

Use the unified stack runner (adds `--opik` to include Opik services):
```bash
./scripts/run_stack.sh start
```

### 4. Access Console

Open: **http://localhost:3000**

Login with `CONSOLE_PASSWORD` from `.env`.

### 5. Create Project

1. Click **Projects** → **New Project**
2. Fill in Title, Thesis, Research Questions
3. Click **Create**

### 6. Upload PDF

1. In project workbench, upload PDF to **Seed Corpus**
2. System automatically processes it
3. View extraction results in **Processing** panel

## Scripts Cheat Sheet

| What | Command |
|------|---------|
| **Preflight check** | `./scripts/preflight_check.sh` |
| **Start** | `./scripts/run_stack.sh start [--opik]` |
| **Stop** | `./scripts/run_stack.sh stop [--opik]` |
| **Merge nodes** | `./scripts/vyasa-cli.sh merge <job_id> <source> <target>` |
| **Run tests** | `./scripts/run_tests.sh` |

## Common Issues

**Services won't start**:
- Check GPU: `nvidia-smi`
- Check ports: `./scripts/preflight_check.sh`
- Check logs: `cd deploy && docker compose logs <service>`

**Orchestrator fails**:
- Ensure ArangoDB is healthy: `curl http://localhost:8529/_api/version`
- Check logs: `docker compose logs vyasa-orchestrator`

**Console won't load**:
- Ensure Orchestrator is healthy: `curl http://localhost:8000/health`
- Check logs: `docker compose logs vyasa-console`

## Next Steps

- Read [Getting Started Guide](docs/runbooks/getting-started.md) for detailed instructions
- Review [System Architecture](docs/architecture/system-map.md) for understanding the system
- Check [Development Guide](docs/guides/development.md) for contributing
