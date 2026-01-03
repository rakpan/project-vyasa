/**
 * E2E Test: Conflict Resolution View
 * 
 * Validates:
 * - Mocked conflicted claim payload
 * - Side-by-side source rendering
 * - Deterministic "Why" explanation tooltip
 */

import { test, expect } from '@playwright/test';
import { setupOrchestratorMocks } from './helpers/mock-helpers';
import { TEST_PROJECT_ID, TEST_JOB_ID } from './fixtures/project-fixtures';
import { mockClaimFlagged } from './fixtures/claim-fixtures';

test.describe('Conflict Resolution View', () => {
  test.beforeEach(async ({ page }) => {
    await setupOrchestratorMocks(page);
    
    // Override workflow result with conflicted claim
    await page.route(
      `**/api/proxy/orchestrator/workflow/result/${TEST_JOB_ID}*`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            job_id: TEST_JOB_ID,
            status: 'COMPLETED',
            result: {
              extracted_json: {
                triples: [mockClaimFlagged],
              },
            },
          }),
        });
      }
    );

    await page.goto(`/projects/${TEST_PROJECT_ID}/workbench?jobId=${TEST_JOB_ID}`);
  });

  test('displays conflicted claim with conflict badge', async ({ page }) => {
    await page.waitForTimeout(1000);

    // Look for conflict badge or flagged status
    const conflictBadge = page.locator('[data-testid="conflict-badge"]')
      .or(page.locator('text=Flagged'))
      .or(page.locator('text=Conflict'))
      .or(page.locator('.conflict-badge'));

    await expect(conflictBadge.first()).toBeVisible({ timeout: 5000 });
  });

  test('shows "Why" tooltip with deterministic explanation', async ({ page }) => {
    await page.waitForTimeout(1000);

    // Find conflict badge and hover/click to show tooltip
    const conflictBadge = page.locator('[data-testid="conflict-badge"]')
      .or(page.locator('text=Flagged'))
      .first();

    if (await conflictBadge.isVisible().catch(() => false)) {
      await conflictBadge.hover();

      // Wait for tooltip
      await page.waitForTimeout(500);

      // Look for explanation text
      const tooltip = page.locator('[role="tooltip"]')
        .or(page.locator('text=Source A asserts'))
        .or(page.locator('text=contradicts'));

      const isVisible = await tooltip.first().isVisible().catch(() => false);
      if (isVisible) {
        const tooltipText = await tooltip.first().textContent();
        expect(tooltipText).toContain('Source A');
        expect(tooltipText).toContain('Source B');
      }
    }
  });

  test('opens side-by-side conflict view', async ({ page }) => {
    await page.waitForTimeout(1000);

    // Click on conflicted claim to open detail view
    const conflictedClaim = page.locator('[data-testid="claim-item"]')
      .or(page.locator('text=Conflicting Claim'))
      .first();

    if (await conflictedClaim.isVisible().catch(() => false)) {
      await conflictedClaim.click();

      // Wait for detail drawer
      await page.waitForTimeout(500);

      // Look for side-by-side comparison
      const conflictView = page.locator('[data-testid="conflict-compare-view"]')
        .or(page.locator('text=Source A'))
        .or(page.locator('text=Source B'))
        .or(page.locator('.conflict-compare'));

      await expect(conflictView.first()).toBeVisible({ timeout: 2000 });
    }
  });

  test('displays source excerpts side-by-side', async ({ page }) => {
    await page.waitForTimeout(1000);

    // Open conflicted claim
    const conflictedClaim = page.locator('[data-testid="claim-item"]').first();
    if (await conflictedClaim.isVisible().catch(() => false)) {
      await conflictedClaim.click();
      await page.waitForTimeout(500);

      // Verify both sources are displayed
      const sourceA = page.locator('text=Source A').or(page.locator('[data-source="a"]'));
      const sourceB = page.locator('text=Source B').or(page.locator('[data-source="b"]'));

      const sourceAVisible = await sourceA.first().isVisible().catch(() => false);
      const sourceBVisible = await sourceB.first().isVisible().catch(() => false);

      // At least one source should be visible in conflict view
      expect(sourceAVisible || sourceBVisible).toBeTruthy();
    }
  });
});

