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
   install verification + click analytics; the npm package, the Cloudflare
   Worker and the WordPress plugin inject tags **server-side**, which is what
   non-JS crawlers (most of them) actually see.
4. **Measure** — every crawler fetch of a preview is an impression; every
   visitor arriving from a social referrer is a click.

Every URL also gets up to three copy angles (benefit / proof / curiosity) you
can serve per link, and cards can be restyled (layout, panel, accent) or
re-rendered per platform size without spending an AI generation.

## Installing on a customer site

Four paths, all of which end with the same tags in the same `<head>`. Pick the
one closest to the traffic:

| Site | Install | Tags rendered |
|---|---|---|
| A Node app (Express, Fastify, Next, Koa, Nest) | `npm install mymetaview` + one line | server-side |
| Behind Cloudflare | Download the generated Worker | edge |
| WordPress | Upload the generated plugin | server-side |
| Anything else (Shopify, Webflow, Squarespace, Wix, Framer, plain HTML) | Paste the snippet tag | in the browser |

The npm package lives in [`packages/mymetaview/`](packages/mymetaview/) and is
the whole integration for a Node app:

```bash
npm install mymetaview
```

```js
const mymetaview = require('mymetaview')

app.use(mymetaview())
```

No key, no build step, nothing to start. It recognises social crawlers, fetches
the card for the URL they asked for, and writes the tags into the top of that
page's `<head>` before the response goes out; everything else passes through
untouched. An app you would rather not edit at all can load it into the process
instead — `NODE_OPTIONS="--require mymetaview/auto"` — and
`npx mymetaview check <url>` answers "did it work?" from the terminal.
[`packages/mymetaview/README.md`](packages/mymetaview/README.md) has the
options, the framework entry points, and the list of things it deliberately
refuses to touch.

The Worker, the plugin and the GTM container are generated pre-bound to the
customer's domain by [`backend/api/v1/routes_install.py`](backend/api/v1/routes_install.py).

Releasing the package (the `mymetaview` name is unclaimed on npm, so the first
publish takes it):

```bash
cd packages/mymetaview
npm test                                   # hermetic: stub API, no network
npm version patch                          # or minor/major
npm publish --access public
```

## Stack

- **Frontend** — React 18 + Vite + TypeScript + Tailwind (`src/`)
- **API** — FastAPI + SQLAlchemy 2 (`backend/`), Postgres in production
  (SQLite for local dev), Redis + RQ for background generation
- **Engine** — Playwright capture, OpenAI-compatible reasoning (single
  art-director pass), HTML/CSS card rendering rasterized in headless
  Chromium, Cloudflare R2 storage (local-disk fallback built in)
- **Integrations** — `packages/mymetaview` (zero-dependency npm package:
  Express/Connect, Fastify and Next.js entry points, plus a `--require` hook),
  and the WordPress plugin / Cloudflare Worker / GTM container generated per
  domain by the API
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
python -m pytest backend/tests             # engine + services (300 tests)
npm run build                              # typecheck + production build
npm run test:e2e                           # Playwright smoke of public pages
npm test --prefix packages/mymetaview      # the npm install path (no network)
```

## The engine

The preview engine is a pipeline of typed stages under
[`backend/services/preview/`](backend/services/preview/) — capture, extraction,
reasoning, composition, rendering, quality. Every generation records the
fallbacks it took, so "why did this card come out generic?" is a query rather
than log archaeology, and the corpus scores the rendered PNGs so a change that
makes cards worse fails CI.

[`docs/ENGINE_ARCHITECTURE.md`](docs/ENGINE_ARCHITECTURE.md) is the map, and
the section at its end lists the things that will bite you.
[`docs/ENGINE_ROADMAP.md`](docs/ENGINE_ROADMAP.md) records why each piece is
the way it is.

## Deployment

Production runs on Railway (API + worker + Postgres + Redis) with Cloudflare
R2 for image storage. See [`docs/ops/DEPLOYMENT.md`](docs/ops/DEPLOYMENT.md)
and the rest of [`docs/ops/`](docs/ops/). Historical planning documents from
earlier development sessions are preserved in [`docs/archive/`](docs/archive/).
