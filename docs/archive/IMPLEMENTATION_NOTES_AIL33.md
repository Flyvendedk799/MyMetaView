# AIL-33: Demo-v2 Production Migration — Implementation Notes

**Handoff for QA (AIL-37)** | Senior Product Engineer

## Summary

Demo page is **fully migrated** to demo-v2. The async job flow (`POST /api/v1/demo-v2/jobs` → poll `GET /api/v1/demo-v2/jobs/{id}/status`) is the production path. Old sync endpoints are deprecated.

## Changes Made

### 1. Frontend (Already Migrated)
- **Demo page** (`src/pages/Demo.tsx`) uses `useDemoGeneration` hook
- **useDemoGeneration** (`src/hooks/useDemoGeneration.ts`) uses `createDemoJob` + `getDemoJobStatus` (demo-v2)
- No frontend changes required — migration was already complete

### 2. API Client Deprecations
- `generateDemoPreview()` — **@deprecated** — uses old `/api/v1/demo/preview` (sync, can timeout)
- `generateDemoPreviewV2()` — **@deprecated** — uses `/api/v1/demo-v2/preview` (sync, can timeout)
- **Production path:** `createDemoJob()` + `getDemoJobStatus()` — no deprecation

### 3. Backend Deprecations
- `POST /api/v1/demo/preview` — **deprecated=True** in OpenAPI, docstring updated
- Endpoint remains functional for backward compatibility; new integrations should use demo-v2 jobs

### 4. Test Script
- `test_demo_after_deploy.ps1` updated to use demo-v2 job flow
- Tests: subpay.dk, stripe.com, futurematch.dk (per task spec)

## Validation Checklist for QA

1. **Demo page**
   - [ ] Navigate to /demo
   - [ ] Enter URL (e.g. https://subpay.dk/)
   - [ ] Verify progress stages display
   - [ ] Verify preview renders on completion
   - [ ] Verify no 60s timeout errors

2. **Test URLs**
   - [ ] subpay.dk
   - [ ] stripe.com
   - [ ] futurematch.dk

3. **API**
   - [ ] `POST /api/v1/demo-v2/jobs` returns job_id
   - [ ] `GET /api/v1/demo-v2/jobs/{id}/status` returns progress then result
   - [ ] Old `/api/v1/demo/preview` still works (deprecated, for backward compat)

## Quick Manual Test (curl)

```bash
# Create job
JOB=$(curl -s -X POST https://www.mymetaview.com/api/v1/demo-v2/jobs \
  -H "Content-Type: application/json" \
  -d '{"url":"https://subpay.dk/"}' | jq -r '.job_id')

# Poll until finished
while true; do
  STATUS=$(curl -s "https://www.mymetaview.com/api/v1/demo-v2/jobs/$JOB/status")
  echo "$STATUS" | jq .
  S=$(echo "$STATUS" | jq -r '.status')
  [ "$S" = "finished" ] || [ "$S" = "failed" ] && break
  sleep 3
done
```

## Files Touched

| File | Change |
|------|--------|
| `src/api/client.ts` | @deprecated on generateDemoPreview, generateDemoPreviewV2 |
| `backend/api/v1/routes_demo.py` | deprecated=True, docstring |
| `test_demo_after_deploy.ps1` | Migrated to demo-v2 job flow, multi-URL |

## Rollback

If issues arise:
- Old `/api/v1/demo/preview` remains available
- Frontend uses demo-v2 exclusively; no rollback path without code revert
