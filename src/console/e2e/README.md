# Vyasa Console E2E Tests

End-to-end tests for the Vyasa Console using Playwright.

## Testing Strategy

These tests validate **UX flows and user-visible behavior**, not business logic. All backend dependencies are mocked at the API boundary to ensure:

- **Deterministic results**: No reliance on real LLMs, databases, or external services
- **Fast execution**: No network delays or processing time
- **Stable tests**: Failures indicate UX contract breaks, not backend issues

## What E2E Tests Cover

✅ User-visible workflows spanning multiple screens  
✅ Routing, navigation, and state transitions  
✅ Presence of key UI states (empty, loading, completed, error)  
✅ Cross-pane interactions (e.g., clicking a claim highlights evidence)

## What E2E Tests Do NOT Cover

❌ LLM behavior or output quality  
❌ Backend orchestration correctness  
❌ Schema validation, precision rules, or governance logic  
❌ Timing-sensitive internal pipelines

Those belong in unit or integration tests.

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

## Test Structure

```
e2e/
├── fixtures/              # Reusable test data
│   ├── project-fixtures.ts
│   ├── ingestion-fixtures.ts
│   ├── claim-fixtures.ts
│   └── manuscript-fixtures.ts
├── helpers/               # Test utilities
│   ├── mock-helpers.ts    # API mocking setup
│   └── test-helpers.ts    # Common assertions
├── 1-project-creation.spec.ts
├── 2-workbench-landing.spec.ts
├── 3-seed-corpus-ingestion.spec.ts
├── 4-knowledge-pane-population.spec.ts
├── 5-conflict-resolution.spec.ts
├── 6-manuscript-context-anchor.spec.ts
└── 7-project-hub-filters.spec.ts
```

## Test Scenarios

### 1. Project Creation (Wizard Flow)
- 3-step wizard navigation
- Template application
- Validation (cannot proceed without ≥1 RQ)
- Redirect correctness

### 2. Workbench Landing (Empty State)
- Redirect to `/projects/{project_id}/workbench`
- All three panes render correct empty states
- Rigor badge visibility

### 3. Seed Corpus Ingestion
- PDF upload (mocked)
- Ingestion cards appear
- State progression: Queued → Extracting → Mapping → Completed

### 4. Knowledge Pane Population
- Mocked claims/triples render
- Linked RQ display
- Provenance breadcrumb
- Status badge

### 5. Conflict Resolution View
- Conflicted claim payload
- Side-by-side source rendering
- Deterministic "Why" explanation tooltip

### 6. Manuscript Context Anchor
- Manuscript block with claim IDs
- Clicking claim ID scrolls evidence pane
- Source span highlighted
- No modal or route change

### 7. Project Hub Views & Filters
- Toggle List ↔ Card view
- Apply rigor filter
- View preference persists across reload

## Mocking Strategy

All API calls are intercepted using Playwright's `page.route()`:

- **Orchestrator API**: Mocked via `/api/proxy/orchestrator/**` routes
- **Deterministic responses**: All fixtures use stable IDs and timestamps
- **State progression**: Simulated via sequential mock responses

See `helpers/mock-helpers.ts` for centralized mocking setup.

## Fixtures

Test data is centralized in `fixtures/`:

- **Project fixtures**: Test project data, templates
- **Ingestion fixtures**: Ingestion states (Queued, Extracting, etc.)
- **Claim fixtures**: Mock triples, claims, conflicts
- **Manuscript fixtures**: Block data, forked blocks

## Best Practices

1. **No timing hacks**: Use `waitFor` and proper selectors, not `setTimeout`
2. **Stable selectors**: Prefer `data-testid` attributes when available
3. **Fallback selectors**: Use `.or()` chains for flexible element finding
4. **Order-independent**: Tests should pass in any order
5. **Clear failures**: Assertions should clearly indicate which UX contract broke

## Debugging

```bash
# Run with Playwright Inspector
npm run test:e2e:debug

# Run with headed browser
npx playwright test --headed

# Run with slow motion
npx playwright test --slow-mo=1000

# Generate trace
npx playwright test --trace on
npx playwright show-trace trace.zip
```

## CI Integration

E2E tests are designed to run in CI:

- Automatic retries on failure
- Screenshot on failure
- HTML report generation
- No external dependencies required (all mocked)

## Adding New Tests

1. Create test file in `e2e/` directory
2. Use fixtures from `fixtures/` for test data
3. Use `setupOrchestratorMocks()` for API mocking
4. Follow existing test patterns for consistency
5. Add to appropriate test file or create new one if needed

## Troubleshooting

**Tests fail with "Element not found"**
- Check if selectors match actual UI (may need to add `data-testid` attributes)
- Verify mock responses are correct
- Use Playwright Inspector to debug

**Tests are flaky**
- Avoid arbitrary timeouts; use `waitFor` instead
- Ensure mocks are set up before navigation
- Check for race conditions in state updates

**Mock responses not working**
- Verify route patterns match actual API calls
- Check network tab in Playwright Inspector
- Ensure mocks are set up in `beforeEach` hook

