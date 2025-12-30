# Test Coverage Summary

## Project-First Async Orchestrator Test Suite

This document summarizes the test coverage for the Project-First async orchestrator implementation.

### Test Files

1. **`test_server.py`** - Legacy tests (updated for Project-First)
   - Basic endpoint tests
   - Project CRUD endpoints
   - Fixed: `test_workflow_submit_failure_project_not_found` now expects 404 (was 202)

2. **`test_server_project_first.py`** - Comprehensive Project-First invariants
   - `/workflow/submit` (JSON): Missing project_id, Project not found, DB unavailable, Success
   - `/workflow/submit` (multipart): All cases including seed_file update and project_context injection
   - Initial state validation
   - Job creation and async thread management

3. **`test_ingest_pdf.py`** - Preview-only endpoint behavior
   - Does NOT return reusable image_paths
   - Response structure validation
   - Invalid file extension handling
   - Missing file handling

4. **`test_workflow_polling_contract.py`** - Polling endpoint contracts
   - `GET /workflow/status/<job_id>`: 404, progress_pct, status fields
   - `GET /workflow/result/<job_id>`: 404, 202 (QUEUED/RUNNING), 500 (FAILED), 200 (SUCCEEDED)
   - Result normalization: `extracted_json.triples` always present

5. **`test_saver_reliability.py`** - Saver failure propagation
   - Saver failures propagate to job status (FAILED)
   - Error messages included in job status
   - No silent success (set_job_result not called on failure)

### Coverage Gaps (Intentionally Not Covered)

- **DB Integration Tests**: All DB operations are mocked. Integration tests are in `test_db.py`.
- **Workflow Node Logic**: Covered in `test_nodes.py`.
- **PDF Processing**: Covered in `test_pdf_parser.py`.
- **Normalization Logic**: Covered in `test_normalization.py`.

### Acceptance Criteria Met

✅ Tests fail if:
- `/workflow/submit` allows projectless submission
- Missing/unknown `project_id` does not return 404/503 appropriately
- Multipart upload does not update seed_files (`add_seed_file` not called)
- `/workflow/result` can return without `extracted_json.triples`
- `/ingest/pdf` returns invalid `image_paths` implying reuse

✅ Tests run without:
- GPUs (all model calls mocked)
- Live DB (all ArangoDB calls mocked)
- Model servers (all SGLang calls mocked)

### Test Collection Stability

- ✅ Lazy imports in `src/orchestrator/__init__.py` prevent import errors during collection
- ✅ All test files use absolute imports (`from src.module import ...`)
- ✅ No heavy initialization at import time
- ✅ All external dependencies are mocked

### Running Tests

```bash
# Run all unit tests
pytest src/tests/unit/

# Run specific test file
pytest src/tests/unit/test_server_project_first.py

# Run with verbose output
pytest src/tests/unit/ -v

# Run with coverage
pytest src/tests/unit/ --cov=src/orchestrator --cov-report=html
```

