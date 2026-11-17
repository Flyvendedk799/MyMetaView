# E2E Tests — Demo Generation Flow

Playwright E2E tests for MyMetaView 6.0 demo generation: batch submit, polling, results.

## Prerequisites

- **Frontend**: `npm run dev` (or use deployed app via `BASE_URL`)
- **Backend**: `uvicorn backend.main:app --reload`
- **Redis** + **RQ workers** (for batch job processing)

Full flow tests (`batch submit`, `polling`, `results`) require the backend and workers to be running.

## Run Tests

```bash
# Local (default: http://localhost:5173)
npm run test:e2e

# Against production
BASE_URL=https://www.mymetaview.com npm run test:e2e

# Interactive UI mode
npm run test:e2e:ui
```

## Test Coverage

| Test | Requires Backend | Description |
|------|------------------|-------------|
| loads demo generation page | No | Smoke test; page loads and form is visible |
| batch submit | Yes | Submit URLs, verify job creation and generating state |
| full flow | Yes | End-to-end: submit → poll → results |
| multiple URLs | Yes | Batch of 2 URLs completes |
| edit URLs | Yes | After results, "Edit URLs" returns to configure |

## Timeouts

- Full flow tests: up to 90s (demo generation can take 30–90s depending on URLs and backend load)
- Default Playwright timeout: 120s

The authenticated product journey has a separate server/configuration:

```bash
# Requires a dedicated Redis database and installed Chromium.
npm run test:journey
```

See `docs/PRODUCT_RELEASE.md` for fixture boundaries, environment overrides,
new migration ordering and the human/live-platform validation still required.
