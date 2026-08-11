# Demo Preview Engine — Comprehensive Final Fix Plan

## Objective
Deliver a demo preview engine that is **reliable**, **visually premium**, **content-faithful**, and **operationally predictable**. The fix is considered complete only when quality is enforced by automated regression gates.

---

## Success Criteria (Definition of Done)

1. **Reliability**
   - Job completion success rate ≥ 99% on golden corpus.
   - 0 unhandled exceptions in preview pipeline execution.
   - 100% failed jobs include a structured failure reason code.

2. **Quality**
   - Mean visual rating improves by at least +1.0 (1–5 scale) versus baseline.
   - Text clipping/overlap defects < 2%.
   - Default/fallback color palette usage reduced by ≥ 50%.

3. **Fidelity**
   - Title/hook fidelity ≥ 85% against manually labeled truth set.
   - Social-proof numeric extraction precision ≥ 80% when numbers are present.

4. **Performance & Cost**
   - P95 end-to-end generation latency reduced by ≥ 25% versus baseline.
   - Token usage per job reduced with no quality regression.

5. **Product UX Trust**
   - “Stuck at 95%” perception eliminated via explicit finalization state.
   - Abandonment rate in 90–100% progress interval decreases measurably.

---

## Phase 0 — Baseline, Corpus, and Freeze (Day 1)

### Tasks
- Build a **golden URL corpus** (minimum 60 URLs) across categories:
  - SaaS landing pages
  - E-commerce PDP/PLP
  - Documentation pages
  - Creator portfolios/blogs
  - Local business pages
- Capture current outputs for each URL:
  - raw screenshot
  - extracted metadata
  - composited preview image
  - pipeline logs
- Record baseline metrics:
  - success/failure rate
  - P50/P95 duration
  - default-color fallback incidence
  - fallback-font incidence
  - human visual rating

### Deliverables
- `docs/demo-engine-baseline.md`
- `artifacts/baseline/<date>/...`
- reproducible run command/script

### Exit Gate
- Baseline report committed; rerunning corpus produces comparable numbers.

---

## Phase 1 — Critical Reliability Fixes (Blocker Phase)

### 1.1 Event loop safety in sync paths
- Replace async loop misuse in sync execution path with proper sync HTTP client usage.
- Ensure no nested event loop assumptions remain.

### 1.2 Retry semantics correctness
- Retries must mutate context (attempt index, prior failures, quality critiques).
- Forbid retries that repeat identical prompt payloads.

### 1.3 Schema/type integrity
- Fix any field defaults that violate declared schema types.
- Add strict validation for core blueprint output fields before render.

### 1.4 Font loading determinism
- Bundle production fonts with explicit path lookup.
- Emit telemetry when fallback font path is used.

### Reliability Invariants
- Every job resolves terminally: `finished` or `failed` within TTL.
- Every fallback branch emits reason code + reason detail.

### Exit Gate
- 0 unhandled exceptions on full corpus.
- Unknown failures < 1%.
- Retry audit shows every retry payload differs from previous attempt.

---

## Phase 2 — Observability and Forensics

### Tasks
- Implement structured per-job trace object:
  - `job_id`, `url`, `start_ts`, `end_ts`
  - stage timings (capture/classify/extract/analyze/compose/quality)
  - extraction confidence and quality-gate sub-scores
  - template selected + rationale
  - palette source (`sampled`, `derived`, `default`)
  - retry_count + retry_deltas
  - terminal status + reason code
- Persist trace for sampling + diagnostics.
- Add developer-facing “job diagnosis” utility.

### Exit Gate
- Any bad preview can be root-caused in <2 minutes from traces.

---

## Phase 3 — Visual Rendering System Upgrade

### 3.1 Template system hardening
- Convert templates (Hero, Modern Card, Profile) into versioned modules.
- Add template contract tests for text/image placement boundaries.

### 3.2 Gradient + contrast modernization
- Use 3-stop gradients with perceptual interpolation.
- Apply adaptive overlays based on local luminance.
- Add optional grain/noise at low opacity for depth.

### 3.3 Typography rendering quality
- Pre-measure layout before draw operations.
- Implement multi-layer shadow/glow policy for high-contrast readability.
- Add letter-spacing rules for large headline sizes.

### 3.4 Composition blending polish
- Replace linear fades with eased masks.
- Tune screenshot blend widths and separator styling.

### Exit Gate
- Visual quality benchmark: +1.0 mean improvement.
- Clipping/overlap <2% on corpus.

---

## Phase 4 — Extraction Fidelity Pipeline

### 4.1 Prompt architecture by page type
- Split monolithic extraction prompt into specialized prompts:
  - general/marketing
  - product/e-commerce
  - profile/personal brand
- Keep output schema concise and strongly validated.

### 4.2 Deterministic post-extraction validators
- Reject low-information hooks (e.g., nav-like or generic phrases).
- Fallback hierarchy for title/hook:
  1. extracted high-confidence hook
  2. `og:title`
  3. first semantic H1
  4. domain-derived fallback

### 4.3 Palette quality rules
- Increase screenshot sampling diversity.
- Enforce minimum perceptual distance between primary/secondary/accent.
- If near-duplicate colors, derive complementary/triadic accent programmatically.

### 4.4 Social-proof extraction pass
- Add regex + DOM pass for numeric proof signals before AI fallback.

### Exit Gate
- Title/hook fidelity ≥ 85%.
- Social-proof numeric precision ≥ 80% where applicable.
- Default palette usage reduced by ≥ 50%.

---

## Phase 5 — Frontend Progress & Error Trust UX

### Tasks
- Replace static 95% plateau behavior with explicit “finalizing” state.
- Show progressive, stage-aware messaging tied to backend reason/status codes.
- Expand error taxonomy:
  - timeout
  - blocked capture
  - extraction failure
  - transient status-check failures
- Defer non-critical popups/prompts until result-consumption milestone.

### Exit Gate
- Reduced abandonment between 90–100% progress.
- “Stuck” complaints near-zero in support telemetry.

---

## Phase 6 — Performance and Cost Guardrails

### Tasks
- Implement dual-lane orchestration:
  - **Fast lane** for simple pages (reduced agent set)
  - **Deep lane** for complex pages (full analysis)
- Add per-job budgets:
  - max AI tokens
  - max stage duration
- Early exit when confidence thresholds are satisfied.
- Hard timeout + graceful fallback path for screenshot capture.

### Exit Gate
- P95 latency reduced by ≥ 25%.
- Lower token/job cost without quality regression.

---

## Phase 7 — Regression Governance (Prevents Re-breakage)

### Tasks
- Nightly golden-corpus runs in CI.
- Visual diffs + metric trend dashboard.
- Release blocker rules for regressions on:
  - success rate
  - latency
  - quality/fidelity metrics
- Require A/B report for template or prompt changes.

### Exit Gate
- CI enforces quality gate; regressions cannot merge silently.

---

## Implementation Sequencing (Recommended)

### Sprint 1
- Phase 0 + Phase 1 + Phase 2

### Sprint 2
- Phase 3 + Phase 4

### Sprint 3
- Phase 5 + Phase 6 + Phase 7

---

## Ownership Model

- **Backend Reliability Lead:** Phases 1, 2, 6
- **Rendering/Design Systems Lead:** Phase 3
- **AI Extraction Lead:** Phase 4
- **Frontend UX Lead:** Phase 5
- **Platform/DevEx Lead:** Phase 7

Each phase should ship with:
- acceptance tests
- before/after metrics
- rollback strategy

---

## Risk Register and Mitigations

1. **Prompt changes improve one category but hurt others**
   - Mitigation: category-stratified corpus scoring and per-category gating.

2. **Rendering quality increases latency**
   - Mitigation: cache intermediate assets and apply fast/deep lanes.

3. **Overfitting to corpus**
   - Mitigation: rotate 20% shadow corpus monthly.

4. **Telemetry noise without actionable dimensions**
   - Mitigation: enforce reason-code taxonomy and trace schema review.

---

## Final Acceptance Checklist

- [ ] Baseline documented and reproducible
- [ ] Reliability blockers fixed and verified
- [ ] Structured traces available for every job
- [ ] Visual quality targets met on corpus
- [ ] Content fidelity targets met on labeled set
- [ ] Progress UX trust issues resolved
- [ ] Performance/cost targets met
- [ ] Nightly regression CI gate enabled

