# Console Navigation Runbook

- Research Workbench requires `projectId` and `jobId`; `pdfUrl` optional. Missing params redirect back to Projects with a toast.
- Interrupts (reframing) surface as overlay with Approve/Resume.
- Manuscript Health tile shows manifest-backed metrics (Words, Claims, Density, Citations, Tables, Figures) and flags; rigor toggle (Exploratory/Conservative) updates ProjectConfig and affects new jobs.
- Sidebar/footer compact summary: shows manifest counts and agent heartbeat; click resume where available.
- Manifest download: available from the Manuscript pane; if no manifest yet, show “No manifest” with refresh.
