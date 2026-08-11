# MyMetaView

Branded link previews for every page of your site — generated automatically,
served to every platform that renders a share card.

Connect a domain, verify it, and MyMetaView captures each page, reads its
content and brand, and composes a real Open Graph card for it (headline,
description, colors, logo, layout). Install once — a snippet, a Cloudflare
Worker, or the WordPress plugin — and shared links on Facebook, X, LinkedIn,
Slack, Discord, and WhatsApp render your cards. Crawler fetches and social
visits are tracked, so the dashboard shows impressions, clicks, and CTR per
domain and per page.

## How it works

1. **Connect & verify a domain** — DNS record, HTML file, or meta tag.
2. **Generate previews** — one URL at a time or your whole sitemap in a bulk
   run. The engine screenshots the page, extracts brand and metadata, has an
   AI art director write the copy and pick a layout, and renders a crisp
   1200×630 card with real typography (plus square/portrait exports).
3. **Install** — the JS snippet covers JS-executing crawlers and powers
   install verification + click analytics; the Cloudflare Worker and the
   WordPress plugin inject tags **server-side**, which is what non-JS
   crawlers (most of them) actually see.
4. **Measure** — every crawler fetch of a preview is an impression; every
   visitor arriving from a social referrer is a click.

Every URL also gets up to three copy angles (benefit / proof / curiosity) you
can serve per link, and cards can be restyled (layout, panel, accent) or
re-rendered per platform size without spending an AI generation.

## Stack

- **Frontend** — React 18 + Vite + TypeScript + Tailwind (`src/`)
- **API** — FastAPI + SQLAlchemy 2 (`backend/`), Postgres in production
  (SQLite for local dev), Redis + RQ for background generation
- **Engine** — Playwright capture, OpenAI-compatible reasoning (single
  art-director pass), HTML/CSS card rendering rasterized in headless
  Chromium, Cloudflare R2 storage (local-disk fallback built in)
- **Billing** — Stripe subscriptions with a 14-day no-card trial

## Local development

Backend (Python 3.11+):

```bash
python -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload          # http://localhost:8000
```

Frontend:

```bash
npm install
npm run dev                                # http://localhost:5173
```

That's enough for the full loop locally: SQLite is the default database,
generated images fall back to local disk when R2 isn't configured, and the
engine degrades gracefully without an `OPENAI_API_KEY` (cards are built from
the page's own metadata). Redis enables caching and background jobs:
`redis-server` + `python -m backend.queue.worker`.

Useful dev environment variables:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Enables AI copy + art direction (optional in dev) |
| `REDIS_URL` | Caching + background job queue |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE` | Use a system Chromium instead of the Playwright-managed download |
| `CAPTURE_USE_ENV_PROXY` / `CAPTURE_IGNORE_TLS_ERRORS` | Capture behind egress proxies (dev only) |
| `ALLOW_PRIVATE_URLS` | Allow capturing localhost fixtures (ignored in production) |

The complete list lives in [`docs/ops/ENVIRONMENT_VARIABLES.md`](docs/ops/ENVIRONMENT_VARIABLES.md).

## Tests

```bash
python -m pytest backend/tests             # engine + services (181 tests)
npm run build                              # typecheck + production build
npm run test:e2e                           # Playwright smoke of public pages
```

## Deployment

Production runs on Railway (API + worker + Postgres + Redis) with Cloudflare
R2 for image storage. See [`docs/ops/DEPLOYMENT.md`](docs/ops/DEPLOYMENT.md)
and the rest of [`docs/ops/`](docs/ops/). Historical planning documents from
earlier development sessions are preserved in [`docs/archive/`](docs/archive/).
