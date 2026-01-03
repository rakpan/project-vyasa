/**
 * Reusable fixtures for ingestion-related test data
 */

import { TEST_PROJECT_ID, TEST_INGESTION_ID } from './project-fixtures';

export const mockIngestionQueued = {
  ingestion_id: TEST_INGESTION_ID,
  project_id: TEST_PROJECT_ID,
  filename: 'test-document.pdf',
  file_hash: 'sha256-hash-12345',
  status: 'QUEUED',
  created_at: '2024-01-15T10:30:00Z',
};

export const mockIngestionExtracting = {
  ...mockIngestionQueued,
  status: 'EXTRACTING',
  progress_pct: 25,
};

export const mockIngestionMapping = {
  ...mockIngestionQueued,
  status: 'MAPPING',
  progress_pct: 50,
};

export const mockIngestionVerifying = {
  ...mockIngestionQueued,
  status: 'VERIFYING',
  progress_pct: 75,
};

export const mockIngestionCompleted = {
  ...mockIngestionQueued,
  status: 'COMPLETED',
  progress_pct: 100,
  first_glance: {
    pages: 10,
    tables_detected: 2,
    figures_detected: 3,
    text_density: 0.85,
  },
  confidence_badge: 'HIGH',
  job_id: 'test-job-67890',
};

export const mockIngestionFailed = {
  ...mockIngestionQueued,
  status: 'FAILED',
  error_message: 'PDF extraction failed: Invalid file format',
};

export const mockJobStatus = {
  job_id: 'test-job-67890',
  status: 'COMPLETED',
  step: 'completed',
  progress: 100,
};

