# Engine and product release

This release adds coherent card edits, crawler delivery checks, editorial evaluation tooling, evidence-based page understanding, a card editor, draft publishing/history, recurring site coverage, durable bulk processing, and source-aware analytics. Security and billing behavior are outside its scope.

## Deploying

1. Apply `alembic upgrade head` to the existing production schema before starting the new API and workers. Five migrations follow `20261101_weekly_digest`: revision numbers, publishing/history, site inventory, durable runs, and traffic attribution. Back up the database as with any schema release.
2. Deploy API and frontend together. Restart the worker supervisor. It schedules enabled site refreshes and recovers abandoned bulk items every minute. Separate bulk worker processes provide capture concurrency; Playwright objects are never shared across capture threads.
3. Verify generation, draft editing and explicit publishing on a connected staging site. Existing cards remain live; their first edit captures the old published image. Existing automatic generation remains automatic until a user begins a manual draft. Publishing offers a switch to enable automatic publication again.
4. Enable recurring coverage per domain in **Site coverage**. Each scan discovers up to 2,000 sitemap URLs, records timestamps, checks known pages, and dispatches bounded per-page checks. Content fingerprints ignore navigation. Canonical aliases stay within the registered host. Missing sitemap entries alone never delete cards; a 404/410 marks an inventory page removed while retaining its last card.
5. Try a bulk run, pause/resume it, and retry failed pages. Running pages finish when paused/cancelled. Queued or running items abandoned for 15 minutes are recovered, with at most three worker-loss attempts. Progress is in SQL; Redis expiration does not remove new bulk histories. Legacy runs remain readable for their original retention period.

## What the checks establish

- `python -m pytest backend/tests -q`: engine and product contracts, failed-render preservation, publication isolation, stale writes, lock preservation, change detection, bulk deduplication and recovery, analytics attribution.
- `npm run build`: TypeScript and production bundle.
- `npm test --prefix packages/mymetaview`: integration package behavior.
- `npm run test:e2e`: existing public-page browser smoke tests.
- `npm run test:journey`: authenticated gallery → generation → editing → publication → crawler-check route → changed-source refresh → failed bulk retry → coverage UI. The API, SQL persistence, renderer and product routes are real. DNS verification, source-page fetching, model output and queue transport use explicit test substitutes. This test does not establish live platform cache behavior, model quality or multi-process production throughput.

For the journey test, start Redis and install both Node and Python dependencies and Chromium. It uses only `work/journey.db`, `work/journey-media`, ports 5174/8015, and a dedicated local Redis database 15, which is cleared at test startup. Set `JOURNEY_PYTHON` if Python is not at `.venv/bin/python`; `JOURNEY_REDIS_URL` selects a dedicated Redis endpoint. `PLAYWRIGHT_CHROMIUM_EXECUTABLE` can point both renderers at a system Chromium. The fixture backend refuses to run without its test flag and isolated database URL; it is never imported by production.

The new migration chain was checked against a schema constructed from the pre-change models, including downgrade and re-upgrade. A completely empty SQLite Alembic install encounters a pre-existing constraint-alteration limitation in the 20250219 organizations migration. Local development may use the existing create-all/schema-sync path; production upgrades start from the existing schema.

## Release validation still requiring real evidence

Run the editorial review workflow in [EDITORIAL_QUALITY.md](EDITORIAL_QUALITY.md) using a live corpus, source pages and actual human ratings. The implementation supplies no invented ratings. Proposed gate: at least 20 reviewed cards across primary page types, at least 90% publishable without edits, and no unsupported factual claims in accepted cards.

Pilot with five representative customer sites. Observe connection, generation, correction, publication and sharing without coaching. Record time to first working share, intervention needed, editing frequency and failures. Verify installed tags with actual platform debuggers and customer integrations. Suggested exit gate: every pilot reaches a valid shared card independently, with any encountered blocking defects fixed. These are proposed release criteria, not results already achieved.

Crawler verification reports current HTTP responses for Facebook, LinkedIn and X; it cannot force a social platform to evict its cache. New analytics distinguish crawler requests and recorded social-referral arrivals. Historical events without source classification remain explicitly unclassified. Audience impressions, unique reach and audience CTR are unavailable. Campaign/variant query labels describe supplied attribution and do not establish randomized experimental lift.
