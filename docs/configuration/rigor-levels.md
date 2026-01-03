# Rigor Levels and Tone/Precision Policies

## Rigor Levels
- **exploratory** (default): light-touch policies; tone is flag-only, precision uses policy defaults.
- **conservative**: stricter posture; can enable tone rewrites when `tone_enforcement: rewrite`.

Set default in `deploy/rigor_policy.yaml` and per-project via `/api/projects/{id}/rigor` or the Workbench UI.

## Changing Rigor Level

### Via Workbench UI
1. Open a project in the Workbench
2. Click the rigor badge (e.g., "exploratory" or "conservative") in the Manifest Bar
3. Select new rigor level in the modal
4. Click "Save Changes"

**Important:** Changes only affect **future jobs**. Currently running or queued jobs will continue with their original rigor level.

### Via API
```bash
# Get current rigor level
GET /api/projects/{project_id}/rigor

# Update rigor level
PATCH /api/projects/{project_id}/rigor
Content-Type: application/json

{
  "rigor_level": "conservative"  # or "exploratory"
}
```

### How It Works
- Rigor level is stored in `ProjectConfig.rigor_level`
- When a new job is created via `/workflow/submit`, the orchestrator:
  1. Fetches the project's `ProjectConfig`
  2. Extracts `rigor_level` from the config
  3. Injects it into the job's `initial_state`
  4. The workflow nodes use this `rigor_level` for tone enforcement and precision policies

## Tone Enforcement
- Modes: `flag_only` (default) or `rewrite`.
- Tone terms defined in `deploy/neutral_tone.yaml` (`hard_ban`, `soft_ban`). Optional `suggestions` may be provided.
- Rewrites (if enabled) only apply for conservative jobs and hard-banned words; citations `[Smith2020]` etc. are preserved.

## Precision Checks
- Detects `INCONSISTENT_DECIMALS` and `EXCESSIVE_PRECISION` per numeric column.
- Uses `max_decimals_default` from `deploy/rigor_policy.yaml` (typically 2 for conservative; higher for exploratory).
- Does **not** invent uncertainty; percentages/units are ignored, comma-separated numbers are normalized.

## Configuration Files
- `deploy/rigor_policy.yaml`: `rigor_level`, `max_decimals_default`, `tone_enforcement`.
- `deploy/neutral_tone.yaml`: tone vocabulary (`hard_ban`, `soft_ban`, optional `suggestions`).
