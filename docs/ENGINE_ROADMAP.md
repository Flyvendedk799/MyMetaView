# Preview Engine — Technical Roadmap

**Scope:** `PreviewEngine` and everything it touches — capture, extraction, AI reasoning,
composition, rendering, quality gating, caching, and the demo/SaaS jobs that drive it.
**Status:** proposal, grounded in the code as of `main` @ Aug 2026.

---

## 1. Where the engine stands today

An honest inventory, because the roadmap only makes sense against it.

### What works

- **One engine, two surfaces.** The demo and the paying dashboard run the same
  `PreviewEngine` with profiles from one table (`quality_profiles.py`). This was hard-won
  (the app previously drifted onto weaker settings) and must be preserved by every change below.
- **The premium renderer is the product.** `premium_card_renderer.py` (real HTML/CSS through
  headless Chromium, Bricolage/IBM Plex design language, composition spec from the
  single-pass art director in `preview_reasoning.py`) produces the cards customers actually see.
- **`render_spec` makes re-renders pure.** Variants, re-rolls, and per-platform sizes can be
  rasterized from the stored spec without re-capturing the page or calling a model.
- **Test substrate exists.** ~200 passing backend tests, a 60+ URL golden corpus
  (`backend/services/preview/corpus/`), a nightly corpus workflow, and typed template
  contracts (`backend/services/preview/templates/contracts.py`).
- **A reason-code taxonomy exists** (`backend/services/preview/observability/reason_codes.py`)
  with a closed enum of terminal outcomes and failure reasons.

### What holds it back

| # | Problem | Evidence |
|---|---------|----------|
| 1 | **God object.** `preview_engine.py` is ~4,100 lines / 44 methods mixing capture, extraction, reasoning, rendering, QA, caching, and R2 uploads. | `backend/services/preview_engine.py` |
| 2 | **Five render stacks, one shipping.** Premium renderer + `enhanced_preview_orchestrator` (7-layer PIL) + `preview_image_generator` (2,250 lines, classic + DNA-aware) + `adaptive_template_engine` (120 KB) + `preview_engine_enhanced`. The PIL stacks are fallbacks that produced the "gradient-only" regression class (docs/MYMETAVIEW_6.5_DEMO_QUALITY_WORKSTREAM.md). | `backend/services/` |
| 3 | **Dead multi-agent path.** `multi_agent=False` in every profile; the orchestrator is documented broken twice (sends `temperature` the gateway model rejects with a 400; fuses metadata with no composition spec, which `_orchestrator_result_is_usable` then rejects). It still costs import weight, config surface, and mental overhead. | `quality_profiles.py` header comment; `demo_preview_job.py` config comment |
| 4 | **Failures are mostly silent.** The engine is laced with broad `try/except → logger.warning → fall through`. The reason-code taxonomy exists but the engine's fallback branches don't emit it, so "why did this card come out generic?" requires log archaeology. | `preview_engine.py` throughout |
| 5 | **Caching is whole-result only.** One Redis entry per URL per lane. No per-domain brand cache, no screenshot cache, and no invalidation when brand settings change — upload a new logo and cached previews keep serving the old card until TTL (48 h demo / 24 h SaaS). | `preview_cache.py`, `preview_pipeline.py` |
| 6 | **Quality critics score intermediates, not the artifact.** The quality loop iterates on scores computed before/around rendering; nothing systematically evaluates the final PNG a human sees (contrast, truncation, logo legibility on panel color). | `quality_orchestrator.py`, engine quality loop |
| 7 | **Model coupling.** `gpt-4o` is hardcoded in `preview_reasoning.py` (5 call sites) and `brand_extractor.py`, despite a provider abstraction (`ai_provider.py`, `openai_compat.py`) existing. |
| 8 | **125 modules in `backend/services/`**, many of which are single-consumer layers of previous quality pushes (`color_psychology`, `texture_engine`, `depth_engine`, `ux_intelligence`, `product_visual_system`, in-tree `test_*_enhancements.py`, …). Nobody can say which are load-bearing. |

### Pipeline as it actually runs

```
demo_preview_job / preview_pipeline (SaaS)
  → PreviewEngine.generate(url)
      1. cache check (whole-result, per lane)
      2. capture: HTML fetch + screenshot (playwright provider, API fallback)
      3. brand extraction ∥ screenshot upload        (brand_extractor)
      4. classification + reasoning (single-pass art director, gpt-4o vision)
      5. quality loop (threshold / soft-pass from profile)
      6. render: premium_card_renderer  ──fail──▶ enhanced orchestrator ──▶ legacy PIL
      7. upload to R2, build render_spec, cache, return
```

---

## 2. Guiding principles

1. **The rendered PNG is the unit of quality.** Every gate, score, and eval should
   ultimately look at what a human sees on Slack/X/LinkedIn, not at intermediate dicts.
2. **One render path.** Degradation should mean *simpler spec into the same renderer*
   (the template lane already proves this works), never *older renderer*.
3. **Nothing new without a corpus delta.** Any change to reasoning, composition, or
   rendering lands with a before/after run on the golden corpus.
4. **Delete before you add.** The engine's biggest quality risk is that its failure
   modes hide in code nobody exercises.

---

## 3. Phase 0 — Measure (1–2 weeks)

You cannot "perfect" what you can't score. Everything later gates on this phase.

### 0.1 Wire the reason-code taxonomy through the engine
- Replace bare `except → warning` in `preview_engine.py`'s stage boundaries with
  `JobTrace` events carrying a `FailureReason`. Every generation terminates
  `finished|failed` with an ordered list of degradations it took
  (e.g. `capture_ok → brand_logo_fallback_favicon → premium_render_ok`).
- Surface the trace in the existing `_debug` block and the admin activity log
  (the plumbing in `demo_preview_job.py` already logs a rich completion entry — extend it,
  don't duplicate it).
- **Acceptance:** for any preview URL, one query answers "which fallbacks fired and why."

### 0.2 Automated visual scoring of the corpus
- Extend the nightly corpus run to keep every rendered PNG and score it mechanically:
  - text truncation / overflow (render at 2× and diff layout boxes),
  - WCAG contrast of title & eyebrow against the actual panel pixels,
  - logo slot occupancy (`_logo_usable`-style check on the final crop, not the input),
  - palette match between card and source screenshot (ΔE against extracted brand colors),
  - "gradient-only" detector (variance of the content region) so the 6.5 regression class
    can never ship silently again.
- Store scores per corpus URL per commit → a trend line, not a vibe.
- **Acceptance:** a PR that regresses corpus visual scores fails CI before a human reviews it.

### 0.3 Stage-level latency + cost accounting
- Per-stage timings already partially exist (`quality_scores.pipeline_stages`); make them
  mandatory and add per-stage AI token/cost from the provider layer
  (`ai_cost_optimizer.py` has the hooks).
- **Acceptance:** p50/p95 per stage and cost-per-preview per lane on a dashboard.

---

## 4. Phase 1 — Consolidate (2–4 weeks)

### 1.1 Single render path
- Make `premium_card_renderer` the only rasterizer. Build a **deterministic minimal spec**
  (title + brand colors + wordmark, the template-lane shape) as the render-time fallback so a
  reasoning failure degrades content, not design language.
- Delete, in order, once corpus shows zero traffic reaches them (Phase 0.1 proves this):
  `enhanced_preview_orchestrator`, `preview_image_generator`'s composited paths,
  `adaptive_template_engine`, `preview_engine_enhanced`, and their single-consumer support
  layers (`texture_engine`, `depth_engine`, `gradient_generator`, `premium_typography_engine`,
  `composition_engine`, …).
- **Risk control:** deletions are mechanical once the reason-code data shows a path fired
  0 times over N days of demo + SaaS traffic.

### 1.2 Delete the multi-agent orchestrator (or fix it behind an eval gate)
- It is off everywhere and rejected when on. Either: (a) remove `enable_multi_agent`, the
  orchestrator, and `agent_executor`'s reasoning chain; or (b) fix the `temperature` /
  composition-spec issues and let it earn its way back **only** by beating the single-pass
  art director on the corpus visual scores. Default recommendation: (a) — the single-pass
  brain plus quality loop is the simpler system to perfect.

### 1.3 Decompose the god object
- Restructure `PreviewEngine` into explicit stages living in the already-started
  `backend/services/preview/` package:
  ```
  preview/
    capture/      # html fetch, screenshot providers, hedging
    extraction/   # brand, palette, social proof (exists)
    reasoning/    # art director, prompts, schemas
    composition/  # spec building, brand-settings overrides, focal crops
    rendering/    # premium renderer + minimal fallback spec
    quality/      # gates, critics, soft-pass policy
    observability/  # (exists)
  ```
  with a typed dataclass contract between each stage (extend `templates/contracts.py`).
  The engine becomes a ~300-line coordinator; each stage is unit-testable without mocks
  of half the world.
- **Acceptance:** `preview_engine.py` under 500 lines; every stage has its own test module;
  no behavioral change on the corpus.

---

## 5. Phase 2 — Reliability & performance (2–3 weeks, overlaps Phase 1)

### 2.1 Stage deadline budgets
- Replace the single 600 s engine timeout with per-stage budgets
  (capture 20 s, extraction 15 s, reasoning 60 s, render 30 s, QA loop bounded by
  remaining budget). A blown stage emits its reason code and degrades instead of
  stalling the whole RQ worker.

### 2.2 Capture hardening
- Hedged screenshot capture: fire the API provider if Playwright hasn't answered in N s,
  take the first success (both providers exist in `screenshot_providers/`; today they are
  sequential fallback).
- Per-domain circuit breaker (module exists: `circuit_breaker.py`) so a hostile/slow domain
  can't burn worker time on every bulk-job URL.

### 2.3 Layered caching with real invalidation
- Split the monolithic cache:
  - **screenshot cache** (URL → R2 key, hours),
  - **brand cache** (domain → logo/colors/name, days) — bulk jobs over one site currently
    re-extract the brand for every URL,
  - **reasoning cache** (content-hash of title+text+screenshot phash → art director output),
  - **result cache** (as today).
- **Invalidate on brand change:** saving brand settings / uploading a logo must bust the
  domain's brand + result caches (`invalidate_brand_settings` exists for settings rows; extend
  it to the preview caches). Today a customer who uploads a logo can wait a day to see it.

### 2.4 Fetch hygiene & safety
- One shared `requests.Session` with retry/backoff and the browser UA (introduced for logos
  in PR #37) for **all** page/image fetches; parallelize logo-candidate downloads
  (they are sequential today — worst case dozens of serial HTTP calls).
- **SSRF guard** on every user-influenced fetch (`logo_url`, target URLs, icon hrefs):
  resolve DNS, refuse private/link-local ranges, cap redirects. The engine fetches
  arbitrary URLs from inside the infrastructure network today.

---

## 6. Phase 3 — Card quality (ongoing, corpus-gated)

Ordered by expected visual impact per effort:

1. **SVG logo rasterization.** SVG is the most common header-logo format and is currently
   skipped (PR #37 made the skip explicit). Add `resvg`/`cairosvg` as an optional dependency;
   rasterize at 2× target size into the normalized-PNG pipeline. Uploaded SVG logos already
   pass through to Chromium; this closes the gap for *scraped* ones and for the
   `logo_base64` demo payload.
2. **Logo-on-panel contrast.** The renderer places the logo on a brand-colored panel with no
   check that it is visible (white logo on white panel is a real failure). At composition
   time: sample the logo's dominant tone vs. the resolved panel color; if contrast < threshold,
   switch panel role, add a subtle plate, or fall back to wordmark. Score it in Phase 0.2.
3. **Critique the pixels.** Point the quality critic (`quality_critic.py`) at the rendered
   PNG with a short vision rubric (readability, balance, brand match) instead of intermediate
   dicts, bounded to 1 iteration by the stage budget. Feed its verdict into soft-pass policy.
4. **Typography & i18n.** Corpus currently skews Latin. Add CJK/RTL/long-German-compound
   URLs to the corpus; verify Noto fallbacks actually load in the render container; define
   truncation rules (title clamp with balanced line breaks) in one place in the renderer.
5. **Template-lane polish.** The metered fallback card is a customer-facing artifact on
   exhausted plans; give it the same corpus scoring and one design pass so "out of AI
   credits" never looks broken.
6. **Focal-crop QA.** `_focal_crop` trusts the art director's box; add a cheap saliency
   check (variance/edge density inside vs. outside the box) and reject crops that grabbed
   nav bars or empty background — reason-coded, falling back to typographic.

---

## 7. Phase 4 — AI strategy & cost (after Phase 1.3)

1. **Finish the provider abstraction.** Route the 6 hardcoded `gpt-4o` call sites through
   `ai_provider.py`; model IDs and parameters (the `temperature` incident) become config,
   selected per stage. This is also what makes gateway/model migrations a config change
   instead of an incident.
2. **Tier by stage.** Vision reasoning is the expensive step; classification, tag extraction,
   and brand-name cleanup do not need the flagship model. Introduce a per-stage model map in
   the profile table (keeping the one-table principle) and let the corpus + cost dashboard
   arbitrate every downgrade.
3. **Structured outputs everywhere.** JSON schemas exist (`backend/prompts/schemas/`);
   enforce them at the provider layer (schema-constrained decoding / function-call format)
   and delete the hand-rolled JSON repair paths.
4. **Reasoning cache** (Phase 2.3) doubles as an eval asset: cached input/output pairs become
   regression fixtures for prompt changes.

---

## 8. Phase 5 — Product-level completeness

- **Per-platform renders from `render_spec`** (OG 1200×630, X summary, LinkedIn, Pinterest):
  a pure-render fan-out job; no model cost. The spec already stores everything needed.
- **Idempotent jobs + retry policy.** DLQ exists (`PreviewJobFailure`); add bounded automatic
  retry for reason codes known to be transient (capture timeouts, provider 5xx) and
  idempotency keys so a retried job can't double-insert variants.
- **Admin "why" view.** Expose the Phase 0.1 trace per preview in the admin panel — the
  activity-log completion entry already carries most of it; render it.
- **Deprecation sweep of `backend/services/`.** After Phase 1 deletions, a `grep`-verified
  dead-module audit with a target of <60 modules. Move the in-tree `test_*_enhancements.py`
  scripts out of the package.

---

## 9. Sequencing

```
Phase 0 (measure) ──────▶ everything else gates on corpus scores + reason codes
Phase 1 (consolidate) ──▶ Phase 4 (model strategy needs the reasoning stage isolated)
Phase 2 (reliability) ──▶ can start alongside Phase 1; cache invalidation is independent
Phase 3 (card quality) ─▶ items 1–2 can ship immediately; 3–6 want Phase 0.2 scoring first
Phase 5 ────────────────▶ any time after Phase 0; per-platform renders need only render_spec
```

**Quick wins shippable this week** (no dependencies): brand-cache invalidation on settings
save (2.3), SSRF guard (2.4), SVG rasterization (3.1), logo/panel contrast check (3.2),
deleting `enable_multi_agent` (1.2a).

## 10. Risks

- **Deleting fallbacks before proving they're dead.** Mitigation: Phase 0.1 reason codes
  give hard traffic counts per path; delete only at zero over a window.
- **Corpus overfitting.** Scores on 60 URLs can be gamed by accident. Mitigation: keep the
  shadow set held out; rotate 10% of the corpus quarterly.
- **Refactor churn vs. shipping.** Phase 1.3 touches everything. Mitigation: strangler
  pattern — new stages land in `backend/services/preview/` and the engine delegates to them
  one at a time, each behind the corpus gate.
