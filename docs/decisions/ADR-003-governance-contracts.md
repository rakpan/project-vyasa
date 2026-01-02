# ADR-003: Governance Contracts and Console Health Surface

- **Status**: Accepted
- **Date**: 2025-01-XX
- **Deciders**: Project Vyasa Team

## Context
Evidence-bound manuscripts need deterministic contracts and clear rigor modes (`exploratory` vs `conservative`). Contracts are enforced in the Orchestrator and surfaced in the Console.

## Decision
- Adopt four contracts: Artifact Manifest, Tone Guard, Precision, Console Health Surface.

## Contracts

### Artifact Manifest Contract
- **Schema**: `ArtifactManifest{ project_id, job_id, created_at, rigor_level, rq_links[], blocks[], tables[], figures[], metrics{ total_words, total_claims, claims_per_100_words, citation_count }, flags[] }`
- **Artifacts**:
  - BlockArtifact: `block_id, rq_id, word_count, claim_ids[], citation_keys[], flags[]`
  - TableArtifact: `table_id, rq_id, source_claim_ids[], precision_contract?, flags[]`
  - FigureArtifact: `figure_id, rq_id, source_claim_ids[], caption, flags[]`
- **Rules**:
  - Every artifact needs `rq_id`; `rq_id="general"` allowed only in exploratory rigor.
  - Tables/Figures need non-empty `source_claim_ids[]`.
  - `claims_per_100_words` computed as `total_claims / (total_words/100)`.
- **Rigor**: Exploratory → flag and continue. Conservative → raise on violations.
- **Persistence**: Arango collection `artifact_manifests` + JSON at `ARTIFACT_ROOT/<project>/<job>/artifact_manifest.json`.
- **Kernel placement**: Manuscript Kernel (artifacts) + Governance Kernel (contract enforcement).

### Tone Guard Contract
- **Detection**: regex over `neutral_tone.yaml`, word boundaries, case-insensitive. Findings: `word, severity(warn|fail), location{start,end}, suggestion, category`.
- **Rigor**: Exploratory → warnings; Conservative → rewrite flagged sentences via Brain with invariants (preserve `claim_ids`, `citation_keys`), re-lint, fail if violations remain.
- **No LLM classification**: LLM only rewrites flagged sentences.
- **Kernel placement**: Governance Kernel.

### Precision Contract
- **Model**: `PrecisionContract{ max_sig_figs, max_decimals, unit_resolution?, rounding_rule(half_up|bankers), consistency_rule(per_column) }`
- **Behavior**: Deterministic numeric formatting; enforce max decimals, sig figs, per-column consistency; round with chosen rule; flag corrections.
- **Rigor**: Exploratory → correct + warn; Conservative → fail if not deterministically correctable.
- **Kernel placement**: Governance Kernel (table validation) + Manuscript Kernel (artifacts).

### Console Health Surface
- **Sources**: ArtifactManifest for active project/job.
- **Surfaces**: Manuscript pane tile (Words, Claims, Density, Citations, Tables, Figures, Flags, rigor toggle); sidebar/footer summary (compact counts + status badge).
- **Rigor toggle**: Writes to ProjectConfig; new jobs read updated rigor.
- **Missing manifest**: show “No manifest yet” with refresh; auto-refresh on update.
- **Kernel placement**: UI to Project Kernel (rigor), Manuscript Kernel (metrics), Governance Kernel (flags).

## Examples
- **Manifest**:
```json
{
  "project_id": "p1",
  "job_id": "j1",
  "rigor_level": "conservative",
  "metrics": { "total_words": 1200, "total_claims": 18, "claims_per_100_words": 1.5, "citation_count": 22 },
  "flags": ["table:t1 missing source_claim_ids"]
}
```
- **Tone finding**:
```json
{ "word": "revolutionary", "severity": "fail", "location": {"start": 12, "end": 25}, "suggestion": "notable" }
```
- **Precision correction**: input `{"a": "1.2345", "b": "foo"}` with `max_decimals=2` ⇒ output `{"a": "1.23", "b": "foo"}`, flag `EXCESSIVE_PRECISION`.

## Status
Accepted.
