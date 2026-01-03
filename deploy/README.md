# Deploying Project Vyasa

## Quick Start (Recommended)

Use the unified stack runner from the project root:

1) Create your env file
```bash
cd deploy
cp .env.example .env
# Edit .env with real values (tokens, passwords, ports, GPU IDs, model paths)
```

2) Start the stack
```bash
# From project root
./scripts/run_stack.sh start

# With Opik (optional observability)
./scripts/run_stack.sh start --opik
```

The `run_stack.sh` script automatically:
- Validates environment configuration
- Creates Docker networks (including `vyasa-net` for Opik)
- Creates data directories (no sudo required)
- Checks for port conflicts
- Starts all services
- Waits for Opik services to be ready (if `--opik` is used)

3) Stop the stack
```bash
./scripts/run_stack.sh stop
# Or with Opik:
./scripts/run_stack.sh stop --opik
```

## Alternative: Manual Deployment

If you prefer to use the deploy scripts directly:

```bash
cd deploy
./start.sh  # Starts Vyasa stack
./stop.sh   # Stops Vyasa stack
```

`start.sh` will:
- Validate `deploy/.env`
- Start docker-compose
- Wait for ArangoDB health
- Seed roles via orchestrator (requires scripts mounted)

## Orchestrator Dependencies

The orchestrator service automatically installs Python dependencies from `requirements.txt` on startup. The `requirements.txt` file is mounted into the container, so no manual installation is needed.

## Opik Integration

When using `--opik`:
- The `vyasa-net` network is created automatically if it doesn't exist
- Opik data directories (`/raid/vyasa/opik_data/*`) are created automatically (Docker handles permissions)
- Port conflicts are detected before starting services
- The script waits for Opik services to be ready before completing

### Opik Environment Variables

Opik requires the following environment variables in `deploy/.env`:

**Required (auto-generated if missing):**
- `OPIK_POSTGRES_PASSWORD` - PostgreSQL password for Opik database. **Auto-generated on first run** using `openssl rand -hex 32` and saved to `deploy/.env`. **MUST be persistent** - changing it will prevent access to existing database data.
- `OPIK_SECRET_KEY` - Secret key for Opik API authentication. **Auto-generated on first run** using `openssl rand -hex 32` and saved to `deploy/.env`. **MUST be persistent** - changing it will invalidate existing sessions.

**Note:** These secrets are automatically generated and saved to `deploy/.env` when you first run `./scripts/run_stack.sh start --opik`. They will persist across restarts. If you need to set them manually, add them to `deploy/.env` or `deploy/.secrets.env` before running the script.

**Optional (with defaults):**
- `OPIK_POSTGRES_USER` - PostgreSQL user for Opik (default: `opik`)
- `OPIK_POSTGRES_DB` - PostgreSQL database name for Opik (default: `opik`)

**Example `.env` entries (if setting manually):**
```bash
# Opik Configuration (auto-generated if not set)
# OPIK_POSTGRES_PASSWORD=your-secure-password-here
# OPIK_SECRET_KEY=your-random-secret-key-here
# Optional - only set if you want to override defaults
# OPIK_POSTGRES_USER=opik
# OPIK_POSTGRES_DB=opik
```

**Security Note:** Never commit `.env` files to version control. These contain sensitive credentials.

## Notes

- `.env` is git-ignored. Keep secrets out of the repo.
- Set `HF_TOKEN`, `CONSOLE_SECRET`, `CONSOLE_PASSWORD`, `NEXTAUTH_SECRET` before deploying publicly.
- `VISION_MAX_IMAGES` controls how many images are OCR'd per PDF (default 5).
- No sudo required: All directory creation and network setup is handled automatically
