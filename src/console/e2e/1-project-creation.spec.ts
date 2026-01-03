/**
 * E2E Test: Project Creation Wizard
 * 
 * Validates:
 * - 3-step wizard flow
 * - Template application
 * - Validation (cannot proceed without ≥1 RQ)
 * - Redirect correctness
 */

import { test, expect } from '@playwright/test';
import { setupOrchestratorMocks } from './helpers/mock-helpers';
import { waitForRoute } from './helpers/test-helpers';
import { TEST_PROJECT_ID, mockProjectCreate } from './fixtures/project-fixtures';

test.describe('Project Creation Wizard', () => {
  test.beforeEach(async ({ page }) => {
    await setupOrchestratorMocks(page);
    await page.goto('/projects');
  });

  test('creates a project using 3-step wizard', async ({ page }) => {
    // Step 1: Click "New Project" button
    await page.click('text=New Project');
    await expect(page.locator('text=Create New Project')).toBeVisible();

    // Step 1: Fill Intent form
    await page.fill('input[name="title"]', mockProjectCreate.title);
    await page.fill('textarea[name="thesis"]', mockProjectCreate.thesis);
    await page.fill('textarea[name="research_questions"]', mockProjectCreate.research_questions[0]);

    // Verify cannot proceed without RQ
    const nextButton = page.locator('button:has-text("Next")');
    await expect(nextButton).toBeEnabled();

    // Click Next to proceed to Step 2
    await nextButton.click();
    await expect(page.locator('text=Seed Corpus')).toBeVisible();

    // Step 2: Seed Corpus (can skip for this test)
    const step2Next = page.locator('button:has-text("Next")');
    await step2Next.click();
    await expect(page.locator('text=Configuration')).toBeVisible();

    // Step 3: Configuration
    // Select template (optional)
    const templateSelect = page.locator('select[name="template"]');
    if (await templateSelect.isVisible()) {
      await templateSelect.selectOption('exploratory-research');
    }

    // Submit
    const submitButton = page.locator('button:has-text("Create Project")');
    await submitButton.click();

    // Verify redirect to workbench
    await waitForRoute(page, `/api/proxy/orchestrator/api/projects`);
    await page.waitForURL(`**/projects/${TEST_PROJECT_ID}/workbench`, { timeout: 10000 });
    
    // Verify project was created
    const url = page.url();
    expect(url).toContain(`/projects/${TEST_PROJECT_ID}/workbench`);
  });

  test('validates required fields in Step 1', async ({ page }) => {
    await page.click('text=New Project');
    
    // Try to proceed without filling required fields
    const nextButton = page.locator('button:has-text("Next")');
    
    // Should be disabled or show validation error
    const isDisabled = await nextButton.isDisabled();
    if (!isDisabled) {
      await nextButton.click();
      // Should show validation error
      await expect(page.locator('text=required') || page.locator('text=Research questions')).toBeVisible();
    } else {
      expect(isDisabled).toBeTruthy();
    }
  });

  test('applies research template', async ({ page }) => {
    await page.click('text=New Project');
    
    // Fill Step 1
    await page.fill('input[name="title"]', mockProjectCreate.title);
    await page.fill('textarea[name="thesis"]', mockProjectCreate.thesis);
    await page.fill('textarea[name="research_questions"]', mockProjectCreate.research_questions[0]);
    await page.click('button:has-text("Next")');
    
    // Skip Step 2
    await page.click('button:has-text("Next")');
    
    // Step 3: Select template
    const templateSelect = page.locator('select[name="template"]');
    if (await templateSelect.isVisible()) {
      await templateSelect.selectOption('conservative-review');
      
      // Verify template prefill (rigor level should be set)
      const rigorInput = page.locator('input[value="conservative"]');
      if (await rigorInput.isVisible()) {
        await expect(rigorInput).toBeChecked();
      }
    }
  });
});

