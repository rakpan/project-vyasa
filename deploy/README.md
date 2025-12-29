# Deploying Project Vyasa

1) Create your env file
```
cp deploy/.env.example deploy/.env
# Edit deploy/.env with real values (tokens, passwords, ports, GPU IDs, model paths)
```

2) Start the stack
```
cd deploy
./start.sh
```
`start.sh` will:
- Validate `deploy/.env`
- Start docker-compose
- Wait for ArangoDB health
- Seed roles via orchestrator (requires scripts mounted)

3) Stop the stack
```
cd deploy
./stop.sh
```

Notes
- `.env` is git-ignored. Keep secrets out of the repo.
- Set `HF_TOKEN`, `CONSOLE_SECRET`, `CONSOLE_PASSWORD`, `NEXTAUTH_SECRET` before deploying publicly.
- `VISION_MAX_IMAGES` controls how many images are OCR’d per PDF (default 5).
