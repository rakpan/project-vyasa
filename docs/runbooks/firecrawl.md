# Firecrawl Cloud Runbook

This runbook covers setup, operation, and testing of Firecrawl Cloud integration for web augmentation.

## Overview

Firecrawl Cloud is an optional service that provides web scraping capabilities for Project Vyasa's web augmentation feature. Vyasa communicates with Firecrawl Cloud via HTTP only, preserving AGPL license boundaries.

**Key Points:**
- Firecrawl Cloud is **optional** - Vyasa core works without it
- Firecrawl Cloud is **opt-in** - must be explicitly enabled via `WEB_AUGMENTATION_ENABLED=true`
- Firecrawl Cloud **requires API key** - sign up at https://firecrawl.dev to get an API key
- Communication is **HTTP-only** - no SDK imports in Vyasa core (preserves AGPL boundaries)
- **Quota limits**: Free tier limited to 500 requests/month; use only for high-fidelity disputes
- **Note**: Local Firecrawl deployment was removed due to instability; Firecrawl Cloud is now required

## Prerequisites

1. **Get Firecrawl Cloud API Key:**
   - Sign up at https://firecrawl.dev
   - Obtain your API key from the dashboard
   - Free tier includes 500 requests/month

2. **Configure environment:**
   ```bash
   # In deploy/.env
   FIRECRAWL_MODE=cloud
   FIRECRAWL_API_KEY=your-api-key-here
   FIRECRAWL_BASE_URL=https://api.firecrawl.dev
   FIRECRAWL_MONTHLY_QUOTA=500
   FIRECRAWL_FAIL_OPEN=false
   WEB_AUGMENTATION_ENABLED=true
   WEB_DOMAIN_ALLOWLIST=.edu,.gov,.org,.com,.net
   WEB_DOMAIN_BLOCKLIST=twitter.com,x.com,facebook.com,instagram.com,linkedin.com,reddit.com
   WEB_MAX_URLS_PER_REQUEST=5
   WEB_CRAWL_ENABLED=false
   ```

## Enabling Firecrawl Cloud

### Configuration

Firecrawl Cloud is enabled via environment variables. No Docker container or local build is required.

```bash
# Set required variables in deploy/.env
FIRECRAWL_API_KEY=your-api-key-here
WEB_AUGMENTATION_ENABLED=true
```

### Verify Configuration

```bash
# Check that API key is set (don't expose the key)
grep -q "FIRECRAWL_API_KEY=" deploy/.env && echo "API key configured" || echo "API key missing"

# Test Firecrawl Cloud connectivity (via integration test)
RUN_FIRECRAWL_TESTS=true pytest src/tests/integration/test_firecrawl_connectivity.py -v
```

## Integration Testing

Firecrawl Cloud integration tests are **opt-in** and require explicit enablement to avoid failures in CI environments where Firecrawl Cloud is not configured.

### Running Integration Tests

1. **Configure Firecrawl Cloud API key:**
   ```bash
   # Set in deploy/.env or export
   export FIRECRAWL_API_KEY=your-api-key-here
   export FIRECRAWL_BASE_URL=https://api.firecrawl.dev
   ```

2. **Set opt-in flag:**
   ```bash
   export RUN_FIRECRAWL_TESTS=true
   ```

3. **Run integration tests:**
   ```bash
   # Run Firecrawl Cloud connectivity tests only
   RUN_FIRECRAWL_TESTS=true pytest src/tests/integration/test_firecrawl_connectivity.py -v
   
   # Run all integration tests (Firecrawl tests will skip if flag not set)
   pytest -m integration -v
   ```

### Test Coverage

The integration test suite (`test_firecrawl_connectivity.py`) validates:

- **API Connectivity**: Firecrawl Cloud API is reachable
- **Scraping**: `FirecrawlBridge.scrape()` for `https://example.com`
  - HTTP 200 response (implicit via successful scrape)
  - Markdown content includes "Example Domain"
  - Result structure is correct
- **Multiple URLs**: Partial success handling
- **Error Handling**: Invalid URLs and failed URLs don't abort batch
- **Quota Handling**: Structured error when quota exceeded (if `FIRECRAWL_FAIL_OPEN=false`)

### Test Behavior

- **Default (CI)**: Tests are **skipped** unless `RUN_FIRECRAWL_TESTS=true`
- **When Enabled**: Tests validate end-to-end connectivity and scraping via Firecrawl Cloud
- **When Firecrawl Unavailable**: Tests skip with clear message

## Troubleshooting

### API Key Not Configured

**Error**: `Firecrawl API key not configured` or `401 Unauthorized`

**Solution**: 
1. Sign up at https://firecrawl.dev to get an API key
2. Set `FIRECRAWL_API_KEY=your-api-key-here` in `deploy/.env`
3. Verify API key is correct: Check Firecrawl Cloud dashboard

### Quota Exceeded

**Error**: `Quota exceeded` or `429 Too Many Requests`

**Solution**:
1. Check quota usage in Firecrawl Cloud dashboard
2. Free tier limited to 500 requests/month
3. Upgrade to paid tier for higher limits
4. Set `FIRECRAWL_FAIL_OPEN=false` to get explicit errors (recommended)
5. Use web augmentation only for high-fidelity disputes to conserve quota

### Connection Errors

**Error**: `Connection error` or `Timeout` when scraping

**Solution**:
1. Verify `FIRECRAWL_BASE_URL=https://api.firecrawl.dev` (default)
2. Check network connectivity to Firecrawl Cloud
3. Verify API key is valid and not expired
4. Check `WEB_TIMEOUT_SECONDS` (default: 30) if timeouts occur

### Tests Skipping Unexpectedly

**Issue**: Tests skip even when Firecrawl Cloud is configured

**Solution**:
1. Ensure `RUN_FIRECRAWL_TESTS=true` is set
2. Verify `FIRECRAWL_API_KEY` is set and valid
3. Check test output for skip reason
4. Test API key manually: `curl -H "Authorization: Bearer $FIRECRAWL_API_KEY" https://api.firecrawl.dev/v0/scrape -d '{"url":"https://example.com"}'`

## Architecture Notes

### HTTP-Only Boundary

Firecrawl Cloud integration maintains strict HTTP-only communication:

- ✅ **Allowed**: `requests.post()` to Firecrawl Cloud API
- ❌ **Forbidden**: `import firecrawl` or any Firecrawl SDK usage

See `docs/CONTRIBUTING.md` (License Boundary / Sidecar Rule) for details.

### Graceful Degradation

When Firecrawl Cloud is unavailable or quota exceeded:

- Web augmentation returns `FAILED` ReviewTask with `reason="firecrawl_unavailable"` or `reason="quota_exceeded"`
- No knowledge graph writes occur
- Errors are logged once (not per-URL)
- Core Vyasa workflows continue normally
- If `FIRECRAWL_FAIL_OPEN=false`, explicit error is returned (recommended)

See `src/orchestrator/web/augmentation_orchestrator.py` for implementation.

### Quota Management

**Strategy**: Use Firecrawl Cloud only for high-fidelity disputes to conserve quota.

- Free tier: 500 requests/month
- Monitor usage in Firecrawl Cloud dashboard
- Set `FIRECRAWL_FAIL_OPEN=false` to fail explicitly when quota exceeded (prevents silent degradation)
- Consider upgrading to paid tier for production use

### Local Deployment Removal

**Note**: Local Firecrawl deployment (Docker sidecar) was removed due to:
- Instability in local builds
- Maintenance burden
- Firecrawl Cloud provides more reliable service

Firecrawl Cloud is now required for web augmentation features.

## Related Documentation

- **Deployment**: `docs/deployment.md` (Firecrawl Cloud section)
- **Configuration**: `docs/configuration/config-reference.md` (Web Augmentation section)
- **Architecture**: `docs/decisions/ADR-004-web-augmentation-sidecar.md`
- **Contributing**: `docs/CONTRIBUTING.md` (License Boundary / Sidecar Rule)

