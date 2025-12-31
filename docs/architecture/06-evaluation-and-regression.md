# Evaluation & Regression Harness (CI-friendly)

Purpose: guard against regressions from context/routing/KV changes with lightweight checks.

## Harness
- Code: `src/tests/eval/test_eval_harness.py`
- Tests include:
  - Schema-valid JSON extraction (triples structure)
  - Citation correctness (source_pointer present with doc_hash + snippet)
  - Determinism (same input → same output within tolerance)
  - Latency budgets at 8k/32k/64k contexts (placeholder delays)

## Baselines
- Latency thresholds (ms): 8k ≤ 500, 32k ≤ 1500, 64k ≤ 3000 (placeholder; tune with real runs)
- Determinism: exact match for identical inputs in this harness
- Schema/citations: required fields must exist

## Running
- Local/CI command:
  ```bash
  pytest src/tests/eval/test_eval_harness.py
  ```

## Notes
- Harness is stubbed (no live model calls) to stay CI-friendly; replace `fake_model_call` with real integration or fixtures when ready.
- Update thresholds when integrating real models to reflect observed performance.*** End Patch>--}}
