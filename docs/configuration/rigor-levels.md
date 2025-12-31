# Rigor Levels and Tone/Precision Policies

## Rigor Levels
- **exploratory** (default): light-touch policies; tone is flag-only, precision uses policy defaults.
- **conservative**: stricter posture; can enable tone rewrites when `tone_enforcement: rewrite`.

Set default in `deploy/rigor_policy.yaml` and per-project via `/api/projects/{id}/rigor`.

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
