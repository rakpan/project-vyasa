# Ingestion API Documentation

## Overview

The Ingestion API provides endpoints for managing file ingestion with duplicate detection, status polling, and retry capabilities.

## Endpoints

### 1. Check Duplicate

**POST** `/api/projects/{project_id}/ingest/check-duplicate`

Check if a file is a duplicate based on SHA256 hash.

**Request Body:**
```json
{
  "file_hash": "a1b2c3d4...",  // SHA256 hex digest (64 chars)
  "filename": "paper.pdf"       // Optional, for logging
}
```

**Response:**
```json
{
  "is_duplicate": true,
  "duplicate_projects": [
    {
      "project_id": "uuid-1",
      "title": "Project Title 1"
    },
    {
      "project_id": "uuid-2",
      "title": "Project Title 2"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid hash format
- `503 Service Unavailable`: Database unavailable

**Hash Format:**
- Must be SHA256 hex digest (64 hexadecimal characters)
- Client calculates hash before upload
- Server verifies hash format

### 2. Get Ingestion Status

**GET** `/api/projects/{project_id}/ingest/{ingestion_id}/status`

Get current ingestion status with first glance summary.

**Response:**
```json
{
  "ingestion_id": "uuid",
  "status": "Extracting",  // Queued | Extracting | Mapping | Verifying | Completed | Failed
  "progress_pct": 45.5,    // 0-100
  "error_message": null,    // Present if Failed
  "first_glance": {         // Present when available (after extraction)
    "pages": 10,
    "tables_detected": 3,
    "figures_detected": 5,
    "text_density": 12.5    // Triples per page
  },
  "confidence_badge": "High"  // High | Medium | Low (after extraction)
}
```

**Status Codes:**
- `200 OK`: Success
- `404 Not Found`: Ingestion not found
- `403 Forbidden`: Ingestion does not belong to project
- `503 Service Unavailable`: Database unavailable

**Status Mapping:**
- `QUEUED` → Queued
- `RUNNING` + `cartographer` → Extracting
- `RUNNING` + `vision` → Mapping
- `RUNNING` + `critic` → Verifying
- `SUCCEEDED` → Completed
- `FAILED` → Failed

**First Glance Summary:**
- Generated automatically when job completes
- Includes page count, tables, figures, text density
- Confidence badge based on evidence ratio and triple count

### 3. Retry Ingestion

**POST** `/api/projects/{project_id}/ingest/{ingestion_id}/retry`

Reset a failed ingestion to Queued status.

**Response:**
```json
{
  "ingestion_id": "uuid",
  "status": "Queued",
  "message": "Ingestion reset to Queued. Please re-upload the file to retry."
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Can only retry failed ingestions
- `404 Not Found`: Ingestion not found
- `403 Forbidden`: Ingestion does not belong to project
- `503 Service Unavailable`: Database unavailable

**Note:** This endpoint only resets the status. The client must re-upload the file via `/workflow/submit` to actually retry.

## Workflow Integration

### Upload Endpoint

**POST** `/workflow/submit`

The workflow submit endpoint now returns `ingestion_id` when a file is uploaded:

**Response:**
```json
{
  "job_id": "uuid",
  "status": "QUEUED",
  "ingestion_id": "uuid"  // Present when file uploaded
}
```

**Ingestion Record Creation:**
- Created automatically when PDF file is uploaded
- File hash calculated before processing
- Linked to job_id after job creation
- Status synced from job status

## Hashing Approach

### Client-Side Calculation

1. Calculate SHA256 hash of file content before upload
2. Send hash to `/ingest/check-duplicate` for duplicate detection
3. Upload file via `/workflow/submit`
4. Server verifies hash matches uploaded file

### Server-Side Verification

1. Calculate hash from uploaded file content
2. Store hash in ingestion record
3. Use hash for duplicate detection across projects
4. Hash is immutable identifier for file content

### Hash Format

- Algorithm: SHA256
- Encoding: Hexadecimal (lowercase)
- Length: 64 characters
- Example: `a1b2c3d4e5f6...`

## Database Schema

### `ingestions` Collection

```json
{
  "_key": "ingestion_id",
  "ingestion_id": "uuid",
  "project_id": "uuid",
  "filename": "paper.pdf",
  "file_hash": "sha256-hex",
  "status": "Queued",
  "job_id": "uuid",
  "error_message": null,
  "progress_pct": 0.0,
  "first_glance": {},
  "confidence_badge": null,
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp"
}
```

**Indexes:**
- `file_hash`: For duplicate detection
- `project_id`: For project queries
- `job_id`: For job lookups

## Confidence Badge Calculation

The confidence badge is calculated based on:

1. **Evidence Ratio**: Percentage of triples with `source_pointer` or `evidence`
2. **Total Triples**: Total number of extracted triples

**Thresholds:**
- **High**: Evidence ratio ≥ 0.8 AND total triples ≥ 10
- **Medium**: Evidence ratio ≥ 0.5 AND total triples ≥ 5
- **Low**: Otherwise

## First Glance Summary

Generated from job result when status becomes `Completed`:

- **pages**: Estimated from raw_text length (~3000 chars per page)
- **tables_detected**: Count of triples mentioning "table"
- **figures_detected**: Count of triples mentioning "figure"
- **text_density**: Triples per page (total triples / pages)

## Error Handling

All endpoints return appropriate HTTP status codes:

- `400`: Invalid input (hash format, missing fields)
- `403`: Authorization error (wrong project)
- `404`: Resource not found
- `500`: Internal server error
- `503`: Service unavailable (database down)

Error responses include:
```json
{
  "error": "Human-readable error message"
}
```

