/**
 * Test helper utilities for common E2E operations
 */

import { Page, expect } from '@playwright/test';

/**
 * Wait for a specific route to be called (useful for verifying API calls)
 */
export async function waitForRoute(
  page: Page,
  urlPattern: string | RegExp,
  timeout = 5000
): Promise<void> {
  await page.waitForResponse(
    (response) => {
      const url = response.url();
      if (typeof urlPattern === 'string') {
        return url.includes(urlPattern);
      }
      return urlPattern.test(url);
    },
    { timeout }
  );
}

/**
 * Wait for element to be visible and stable (no layout shifts)
 */
export async function waitForStableElement(
  page: Page,
  selector: string,
  timeout = 5000
): Promise<void> {
  const element = page.locator(selector);
  await element.waitFor({ state: 'visible', timeout });
  // Small delay to ensure no layout shifts
  await page.waitForTimeout(100);
}

/**
 * Verify empty state is displayed
 */
export async function expectEmptyState(
  page: Page,
  containerSelector: string,
  expectedText?: string
): Promise<void> {
  const container = page.locator(containerSelector);
  await expect(container).toBeVisible();
  
  if (expectedText) {
    await expect(container).toContainText(expectedText);
  }
}

/**
 * Verify loading state is displayed
 */
export async function expectLoadingState(page: Page, selector: string): Promise<void> {
  const loading = page.locator(selector);
  await expect(loading).toBeVisible();
}

/**
 * Verify error state is displayed
 */
export async function expectErrorState(
  page: Page,
  containerSelector: string,
  expectedError?: string
): Promise<void> {
  const container = page.locator(containerSelector);
  await expect(container).toBeVisible();
  
  if (expectedError) {
    await expect(container).toContainText(expectedError);
  }
}

/**
 * Click and wait for navigation (with route verification)
 */
export async function clickAndWaitForNavigation(
  page: Page,
  selector: string,
  expectedRoute: string | RegExp
): Promise<void> {
  const [response] = await Promise.all([
    page.waitForResponse((resp) => {
      const url = resp.url();
      if (typeof expectedRoute === 'string') {
        return url.includes(expectedRoute);
      }
      return expectedRoute.test(url);
    }),
    page.click(selector),
  ]);
  
  expect(response.ok()).toBeTruthy();
}

