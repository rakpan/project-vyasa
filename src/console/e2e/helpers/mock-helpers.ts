/**
 * Centralized mock helpers for API responses
 * Intercepts Next.js API routes and returns deterministic fixtures
 */

import { Page, Route } from '@playwright/test';
import {
  mockProject,
  TEST_PROJECT_ID,
  TEST_JOB_ID,
} from '../fixtures/project-fixtures';
import {
  mockIngestionQueued,
  mockIngestionCompleted,
  mockJobStatus,
} from '../fixtures/ingestion-fixtures';
import { mockWorkflowResult } from '../fixtures/claim-fixtures';

/**
 * Setup API route mocking for orchestrator proxy
 */
export async function setupOrchestratorMocks(page: Page) {
  // Mock GET /api/projects/{id}
  await page.route(
    `**/api/proxy/orchestrator/api/projects/${TEST_PROJECT_ID}`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockProject),
      });
    }
  );

  // Mock POST /api/projects (create)
  await page.route('**/api/proxy/orchestrator/api/projects', async (route: Route) => {
    if (route.request().method() === 'POST') {
      const postData = route.request().postData();
      const requestBody = postData ? JSON.parse(postData) : {};
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...mockProject,
          id: TEST_PROJECT_ID,
          title: requestBody.title || mockProject.title,
          thesis: requestBody.thesis || mockProject.thesis,
          research_questions: requestBody.research_questions || mockProject.research_questions,
        }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/projects (list)
  await page.route('**/api/proxy/orchestrator/api/projects*', async (route: Route) => {
    if (route.request().method() === 'GET' && !route.request().url().includes('/projects/')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          active: [mockProject],
          archived: [],
        }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock POST /workflow/submit
  await page.route('**/api/proxy/orchestrator/workflow/submit', async (route: Route) => {
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: TEST_JOB_ID,
        ingestion_id: 'test-ingestion-abcde',
        status: 'PENDING',
      }),
    });
  });

  // Mock GET /workflow/result/{job_id}
  await page.route(
    `**/api/proxy/orchestrator/workflow/result/${TEST_JOB_ID}*`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockWorkflowResult),
      });
    }
  );

  // Mock GET /workflow/status/{job_id}
  await page.route(
    `**/api/proxy/orchestrator/workflow/status/${TEST_JOB_ID}*`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockJobStatus),
      });
    }
  );

  // Mock GET /api/projects/{id}/ingest/{ingestion_id}/status
  await page.route(
    `**/api/proxy/orchestrator/api/projects/${TEST_PROJECT_ID}/ingest/*/status`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockIngestionCompleted),
      });
    }
  );

  // Mock POST /api/projects/{id}/ingest/check-duplicate
  await page.route(
    `**/api/proxy/orchestrator/api/projects/${TEST_PROJECT_ID}/ingest/check-duplicate`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          is_duplicate: false,
          duplicate_projects: [],
        }),
      });
    }
  );

  // Mock PATCH /api/projects/{id}/rigor
  await page.route(
    `**/api/proxy/orchestrator/api/projects/${TEST_PROJECT_ID}/rigor`,
    async (route: Route) => {
      if (route.request().method() === 'PATCH') {
        const requestBody = route.request().postData() 
          ? JSON.parse(route.request().postData() || '{}')
          : {};
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            project_id: TEST_PROJECT_ID,
            rigor_level: requestBody.rigor_level || 'exploratory',
          }),
        });
      } else {
        await route.continue();
      }
    }
  );
}

/**
 * Setup ingestion state progression mocks
 */
export async function setupIngestionStateProgression(
  page: Page,
  ingestionId: string,
  states: Array<'QUEUED' | 'EXTRACTING' | 'MAPPING' | 'VERIFYING' | 'COMPLETED'>
) {
  let stateIndex = 0;

  await page.route(
    `**/api/proxy/orchestrator/api/projects/${TEST_PROJECT_ID}/ingest/${ingestionId}/status`,
    async (route: Route) => {
      const state = states[stateIndex] || states[states.length - 1];
      const progressMap: Record<string, number> = {
        QUEUED: 0,
        EXTRACTING: 25,
        MAPPING: 50,
        VERIFYING: 75,
        COMPLETED: 100,
      };

      const mockState = {
        ingestion_id: ingestionId,
        project_id: TEST_PROJECT_ID,
        filename: 'test-document.pdf',
        status: state,
        progress_pct: progressMap[state],
        ...(state === 'COMPLETED' && {
          first_glance: {
            pages: 10,
            tables_detected: 2,
            figures_detected: 3,
            text_density: 0.85,
          },
          confidence_badge: 'HIGH',
        }),
      };

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockState),
      });

      // Advance to next state on next call (simulates polling)
      if (stateIndex < states.length - 1) {
        stateIndex++;
      }
    }
  );
}

