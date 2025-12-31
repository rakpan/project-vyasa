# Opik Offline Evaluation Scripts

Purpose: Generate tone/precision datasets from existing Vyasa artifacts and optionally submit to Opik evaluations. These scripts are offline utilities and **do not affect Vyasa runtime**.

## Scripts
- `build_tone_dataset.py [input_jsonl] <output_jsonl>`  
  - Reads manuscript blocks or ArtifactManifests (JSONL) or, if no input provided, best-effort from ArangoDB.  
  - Labels blocks as `sensational` (hard tone flags) or `neutral`.

- `build_precision_dataset.py [input_jsonl] <output_jsonl>`  
  - Reads tables (JSONL/ArtifactManifests) or, if no input provided, best-effort from ArangoDB.  
  - Emits rows per precision flag (table_id, column, issue, values, rigor_level).

- `run_evals.py <dataset_jsonl>`  
  - If `OPIK_ENABLED=true` and `OPIK_BASE_URL` set, submits to Opik eval endpoint (best effort).  
  - Otherwise prints a local summary (counts/label distribution).

## How to Run Locally
```bash
# Tone dataset
python scripts/opik/build_tone_dataset.py data/blocks.jsonl out/tone.jsonl

# Precision dataset
python scripts/opik/build_precision_dataset.py data/tables.jsonl out/precision.jsonl

# Offline eval summary (no Opik required)
python scripts/opik/run_evals.py out/tone.jsonl
```

## Enabling Opik (optional)
Set env vars:
- `OPIK_ENABLED=true`
- `OPIK_BASE_URL=http://127.0.0.1:56500` (or your Opik endpoint)
- `OPIK_API_KEY` if required
- `OPIK_PROJECT_NAME=vyasa` (default)

If Opik is unavailable, scripts continue with local summaries.

## Safety
- No changes to orchestrator/workflow/nodes.
- Best-effort DB access; JSON file inputs are preferred for portability.
- No prompts or sensitive content are required by these scripts.
