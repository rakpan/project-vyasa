# Project Vyasa User Guide (Researcher Experience)

## Job Progress (What you see while processing)
- After uploading a PDF, the Console polls `/jobs/{job_id}/status` every ~2s.
- The header shows the current step (e.g., “Analyzing Visuals...”) and a progress bar.
- If a job fails, a red alert shows the specific error; otherwise it completes at 100%.
- _Screenshot placeholder_: “Job Progress panel with step label and progress bar.”

## Verifying Results
- Extracted claims/triples now show confidence badges:
  - Green ≥ 0.8 (High), Yellow 0.5–0.79 (Medium), Red < 0.5 (Low).
- Each claim can expand to reveal the evidence snippet sent by the orchestrator.
- _Screenshot placeholder_: “Claim list with confidence badges and expanded evidence.”

## Tips
- Always select an active project before uploading (Project-First invariant).
- If progress stalls, check the orchestrator logs or `/jobs/{id}/status` for errors.
