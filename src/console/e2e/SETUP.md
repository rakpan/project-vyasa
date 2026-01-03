# E2E Test Setup Instructions

## Prerequisites

The E2E tests require Node.js and npm to be installed. These tests use Playwright, which needs to be installed as a dependency.

## Installation

```bash
cd src/console
npm install
npx playwright install
```

## Running Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run with UI mode (interactive)
npm run test:e2e:ui

# Run in debug mode
npm run test:e2e:debug

# Run specific test file
npx playwright test e2e/1-project-creation.spec.ts
```

## Note on run_tests.sh

The `scripts/run_tests.sh` script is designed for Python unit/integration tests. E2E tests are separate and require Node.js/npm to run.

To run E2E tests, use the npm scripts above or run Playwright directly.

## Fixed Issues

1. **postDataJSON() method**: Fixed to use `postData()` and manual JSON parsing, as `postDataJSON()` is not available in Playwright's Request API.

2. **Unused imports**: Removed unused imports from test files.

3. **Web server config**: Made webServer optional in CI environments.

