# Artifact Manifests (Saver Output)

What: A deterministic JSON record of generated assets and rigor signals for a job.

Where it is written:
- Filesystem: `/raid/artifacts/{project_id}/{job_id}/artifact_manifest.json` (configurable via `ARTIFACT_ROOT`)
- ArangoDB: `artifact_manifests` collection

When: Saver node / job completion (best-effort; job does not fail if manifest persistence fails).

Contents:
- `blocks`: per-block stats (word_count, citation_count, tone flags, supported_by)
- `tables`: table artifacts with precision flags and unit verification status
- `visuals`: figures/diagrams/table images with optional source bbox
- `totals`: aggregate counts (words, citations, tables, figures)
- `rigor_level`: exploratory or conservative, copied from project/job settings

Telemetry:
- `artifact_manifest_written` on success
- `artifact_manifest_failed` on failure (job continues)
