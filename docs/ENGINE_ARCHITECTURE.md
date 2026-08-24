# Preview Engine — architecture

What `ENGINE_ROADMAP.md` proposed, as it now stands. The roadmap is kept beside
this as the record of *why*; this describes the engine you will actually read.

---

## The shape

```
backend/services/
  preview_engine.py          the public surface: config in, result out (407 lines)
  premium_card_renderer.py   the one rasterizer — HTML/CSS through Chromium
  preview_reasoning.py       the single-pass art director

  preview/
    pipeline.py              the coordinator: the order the stages run in
    stages.py                the typed contract between them
    budgets.py               per-stage deadlines
    retry.py                 what gets retried, and idempotency

    capture/                 screenshot + HTML, hedged across providers
    extraction/              brand identity, logo candidate resolution
    reasoning/               the art director's model map and output contract
    composition/             turning a request into a renderable fact
    rendering/               the renderer call, the spec, typography rules
    quality/                 pixel metrics, soft-pass policy, the vision critic
    caching/                 four layers, and their invalidation
    net/                     one guarded, pooled HTTP session
    assets/                  SVG rasterization, logo contrast, focal crops
    observability/           reason codes, job traces, diagnosis
    corpus/                  the golden URLs and their scoring
```

Each stage is a function between two dataclasses. Testing one means building a
small object rather than standing up a browser, a vision model and an object
store — which is why `backend/tests/test_preview_stages.py` runs in under a
second.

## The pipeline

```
cache → capture → classify → (extract ∥ upload) → reason → compose → render → grade
```

Four rules it enforces, none of which lived anywhere legible before:

**Every stage has a deadline**, clamped to what remains of the total. One 600s
timeout is a hang detector, not a budget: a stalled capture burned ten minutes
of a worker and no stage ever got the chance to degrade.

**Every fallback records a degradation code.** A finished generation carries an
ordered trail:

```
capture_ok → brand_logo_fallback_favicon → composition_focal_crop_rejected
           → premium_render_ok → quality_pass
```

A job that limped through five fallbacks and one that sailed through were
otherwise the same "success". The trail is in the job trace, both activity logs,
and the Admin → Engine page, which renders each step as a sentence.

**Degradation means a simpler spec into the same renderer**, never an older
renderer. When reasoning fails, `build_minimal_spec` composes title, brand
colours and wordmark with no model call, and the premium renderer draws it. The
four PIL stacks that produced the "gradient-only" regression class are gone.

**The thing that gets graded is the rendered PNG** — including the fallback.

## Quality

`preview/quality/pixel_metrics.py` measures the artefact:

| measurement | catches |
|---|---|
| title / eyebrow contrast | white-on-white type (WCAG ratio from real pixels) |
| overflow | copy clipped at the safe-area edge |
| logo occupancy | a smudge in the corner where a mark should be |
| palette ΔE | a card whose colours have nothing to do with the site |
| gradient-only | the 6.5 regression: a pretty gradient, no content |
| balance | everything crammed in one corner |

Two things it deliberately does **not** score as defects, because both are
design choices and the gate acts on these numbers:

- **An absent logo.** A brand with no mark renders the wordmark. Pass
  `expect_logo=False`.
- **A bleeding panel.** A `split` or `product` card's visual reaches three edges
  on purpose. Pass `layout`; the engine always knows it.

The policy in `quality/policy.py` asks two separate questions. *Is it broken?* —
answered from pixels, and no threshold argues a broken card into acceptability.
*Is it good enough?* — the profile's numbers, where a below-target card can
still soft-pass, because a slightly weak real card beats a fallback that is
generic by construction.

## Models

`preview/reasoning/models.py` is the one table. Purposes name what they need;
the table says which model answers and with what parameters; `PREVIEW_MODEL_*`
env vars override, so a migration is a deploy variable rather than a release.

Vision reasoning runs on the flagship because it is reading a screenshot and
authoring a composition. Classification, tag extraction and brand-name cleanup
do not, and paying flagship rates for them was most of the per-preview cost.

`ModelSpec.supports_temperature` is how the gateway's rejected parameters became
config. `openai_compat` remains as a net for paths not yet converted, and now
logs a warning naming the caller when it drops something.

## Caching

Four layers, each keyed by what actually determines it:

| layer | key | TTL |
|---|---|---|
| screenshot | URL | 6h |
| brand | **domain** | 7d |
| reasoning | content hash + model + prompt version | 14d |
| result | URL + lane | 24h / 48h demo |

Keying brand by domain is what makes a bulk job over one site extract its brand
once rather than once per URL. Saving brand settings or uploading a logo clears
the domain's brand cache and the org's cached previews — before that, a customer
who uploaded a logo waited out the TTL and reasonably concluded it had failed.

The reasoning cache doubles as an eval asset: every entry is a real page's
art-director output under the current prompt. `replay_reasoning` reads them as a
regression baseline. **Bump `PROMPT_VERSION` in `reasoning/stage.py` when you
edit a prompt**, or the run will serve output the previous prompt authored.

## Safety

Every outbound fetch goes through `preview/net`, which resolves the host and
refuses anything not globally routable, re-guards each redirect hop, and pools
connections behind one browser-UA session with retry and backoff. The engine
runs inside the infrastructure network, so "fetch this URL" was also "reach this
private address".

A host that *does not resolve* raises `UnresolvableHost` rather than a plain
refusal: that is a transient network failure, and the retry policy treats the
two oppositely.

## Regression gate

`backend/scripts/preview_engine/run_corpus.py` runs the golden corpus, keeps
every rendered PNG, scores its pixels, records a trend point against the commit,
and compares against a stored baseline.

```bash
# nightly: run, score, record the trend, promote to baseline if clean
python -m backend.scripts.preview_engine.run_corpus \
    --output-dir artifacts/baseline --update-baseline

# PR: a capped slice, gated
python -m backend.scripts.preview_engine.run_corpus \
    --output-dir artifacts/pr --gate --max-urls 12
```

`--gate` fails on a regression and names the URLs. Nightly promotes a run to
baseline only when it did not regress, so a bad night cannot quietly become the
new normal. Absolute floors sit underneath the comparison so slow drift cannot
land somewhere unacceptable.

Twelve non-Latin URLs are in the main corpus, not an opt-in slice: a typography
change that breaks CJK should fail the ordinary run.

## Where to look when a card is wrong

1. **Admin → Engine** — recent generations, filterable to the degraded ones.
   Each shows its trail as sentences plus per-stage time and cost.
2. The job id in the activity log (`job_trace_id`) opens one trace directly.
3. `GET /api/v1/preview-diagnosis/cost` — p50/p95 and spend per stage and lane.
4. Traces live 48 hours in Redis.

## Local development

```bash
pytest backend/tests                     # ~300 tests, no network, no browser
python -m backend.scripts.preview_engine.run_corpus --dry-run
```

The renderer needs Chromium. When Playwright's managed download is absent or a
different version, point at a system binary:

```bash
export PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chrome
```

`cairosvg` is optional — without it, scraped SVG logos fall back to the
wordmark rather than failing.

## Things that will bite you

- **Bump `PROMPT_VERSION`** when editing an art-director prompt, or the
  reasoning cache serves the old prompt's output.
- **Pass `layout` to `score_card`** from anywhere inside the engine. Without it
  a split card's panel reads as overflow.
- **The corpus baseline lives in CI cache**, not the repo. A fresh branch has no
  baseline and the first run establishes one rather than failing.
- **`enable_multi_agent` is gone.** So is the orchestrator. Tests assert its
  absence; that is deliberate.
