# Plan: Fix All Demo Issues & Drastically Improve Generation Quality

## Root Cause Analysis

After thorough analysis of the entire codebase, I've identified the following categories of issues:

### Category A: Critical Bugs That Break the Demo
### Category B: Generation Quality Issues (the images look bad)
### Category C: AI Extraction Issues (wrong/weak content extracted)
### Category D: Frontend UX Issues

---

## Phase 1: Fix Critical Demo Bugs

### 1.1 Fix asyncio event loop crash in ReadabilityAutoFixer
**File:** `backend/services/preview_engine.py:801-809`
**Bug:** Uses `asyncio.get_event_loop().run_until_complete()` inside a sync context which crashes when no event loop exists (or when running inside an existing loop). This kills the visual quality fix path silently.
**Fix:** Replace with synchronous `httpx.Client` (no async needed - we're already in a sync thread).

### 1.2 Fix quality gate retry loop re-running identical AI reasoning
**File:** `backend/services/preview_engine.py:724-727`
**Bug:** When quality gates fail, the retry calls `_run_ai_reasoning_enhanced()` with identical parameters, getting identical results. Retries are wasted.
**Fix:** Pass retry context (attempt number, previous failures, quality suggestions) to the AI reasoning call so it can adjust its approach.

### 1.3 Fix `overall_quality` type mismatch in LayoutBlueprint
**File:** `backend/api/v1/routes_demo_optimized.py:501`
**Bug:** `overall_quality` is set from `blueprint.get("overall_quality", 0.0)` but the Pydantic model expects `str` (e.g., "good", "excellent"). A float default causes validation errors or silent type coercion.
**Fix:** Use `str` default: `blueprint.get("overall_quality", "good")`.

### 1.4 Fix silent font loading failures
**File:** `backend/services/preview_image_generator.py` - `_load_font()`
**Bug:** Font loading silently falls back to PIL's default bitmap font (ugly, tiny, no bold). This makes previews look broken when running on servers without the expected fonts installed.
**Fix:** Bundle a high-quality open-source font (Inter or similar) in the repo and reference it by absolute path. Add explicit logging when fallback is used.

---

## Phase 2: Drastically Improve Image Generation Quality

### 2.1 Redesign the Hero template for visual impact
**File:** `backend/services/preview_image_generator.py:573-829`
**Problems:**
- Gradient backgrounds look generic (every preview looks the same shape)
- Text shadow is only 2px (barely visible, doesn't ensure readability)
- Logo placed on white square background looks amateurish
- Badge positioning can overlap with logo
- No visual hierarchy differentiation (heading and subtitle too similar in weight)
- Content can overflow the left panel or leave too much empty space

**Fixes:**
- Add a semi-transparent dark overlay on the gradient for guaranteed text contrast
- Increase text shadow to 3-4px with blur effect (draw shadow text slightly offset with lower opacity)
- Remove white box behind logo; use the logo with a subtle drop shadow instead
- Add proper vertical spacing algorithm: measure all content first, then distribute space evenly
- Make subtitle visually distinct: lighter weight, different opacity, smaller relative size
- Add a subtle noise/grain texture to gradients to make them feel more premium
- Ensure badge never overlaps logo by tracking occupied regions

### 2.2 Improve gradient generation
**File:** `backend/services/preview_image_generator.py` - `_draw_gradient_background()`
**Problem:** Diagonal gradients between two similar colors look flat and boring.
**Fix:**
- Add a third color stop (derived from accent color at 30% opacity) for depth
- Use perceptual color interpolation (LAB space) for smoother gradients
- Add subtle radial highlight in top-left quadrant for dimension

### 2.3 Fix screenshot panel blending
**File:** `backend/services/preview_image_generator.py:613-646`
**Problem:** The linear fade mask creates a harsh transition. Screenshot panel sometimes shows cookie banners or loading states.
**Fix:**
- Use a curved (ease-in) fade mask instead of linear
- Increase fade width from 120px to 180px for smoother blending
- Apply subtle brightness/contrast boost to screenshot panel to match gradient vibrancy
- Add a very thin vertical separator line (1px, white at 15% opacity) at the blend point

### 2.4 Improve text rendering quality
**Files:** `backend/services/preview_image_generator.py:174-344, 736-783`
**Problems:**
- Text wrapping doesn't account for descenders (g, y, p) causing clipping
- No letter-spacing control (text looks cramped at large sizes)
- White text on light gradients can be unreadable

**Fixes:**
- Add a text contrast check: if gradient luminance > 0.5 at text position, add darker overlay behind text area
- Implement multi-layer text rendering: dark shadow layer → medium shadow layer → white text (creates a "glow" effect for readability)
- Add 1-2px tracking (letter spacing) for headlines above 60px

### 2.5 Improve Modern Card and Profile templates
**Problems:** These templates are less polished than Hero.
**Fixes:**
- Modern Card: Add subtle box shadow to the card, refine the accent bar to be a left-side vertical bar instead of bottom, improve typography hierarchy
- Profile: Better avatar border (gradient border instead of plain white), add a subtle pattern/texture to the header gradient

---

## Phase 3: Improve AI Extraction Quality

### 3.1 Improve the main extraction prompt (STAGE_1_2_3_PROMPT)
**File:** `backend/services/preview_reasoning.py:252+`
**Problems:**
- Prompt is extremely long (~500 lines) which dilutes focus
- Too many instructions compete for attention
- Product page extraction is mixed in with general extraction
- The "chain of thought" instructions say "don't output these" but the model needs structured thinking

**Fixes:**
- Split into focused prompts by page type (general, product, profile)
- Move product-specific instructions to a separate prompt used only when page is classified as product/ecommerce
- Trim redundant examples and repetitive instructions
- Make the output schema more concise and structured
- Add stronger instructions for color extraction (hex codes from visible UI, not guesses)

### 3.2 Fix color extraction producing generic/bland palettes
**File:** `backend/services/brand_extractor.py:611-845`
**Problem:** Color extraction often returns the default blue (#2563EB) or very similar primary/secondary colors, making all previews look the same.
**Fixes:**
- Increase the color sampling from screenshot (more pixels, better distribution)
- Require minimum color distance between primary, secondary, and accent (deltaE > 30 in LAB space)
- If extracted colors are too similar, derive secondary from primary by shifting hue ±30°
- Derive accent as a complementary or triadic color
- Add website-category-aware color defaults (tech=blue/purple, food=warm/orange, health=green/teal)

### 3.3 Improve title/hook extraction
**Problem:** AI often extracts generic text like "Welcome to..." or navigation text.
**Fix:** Add post-extraction validation that rejects known-bad patterns and falls back to og:title or the first H1 from DOM data. The DOM data extraction (`raw_top_texts`) is already available but underutilized.

### 3.4 Better social proof extraction
**Problem:** Social proof often lacks specific numbers or extracts irrelevant items.
**Fix:** Add a dedicated social proof scanning pass that specifically looks for numeric patterns (regex for ratings, review counts, user counts) in the HTML before falling back to AI extraction.

---

## Phase 4: Frontend UX Improvements

### 4.1 Fix progress bar stalling at 95%
**File:** `src/pages/Demo.tsx:481`
**Problem:** Progress is capped at 95% until job finishes, making it appear frozen.
**Fix:** After reaching 95%, show a pulsing "Finalizing..." animation instead of a static progress bar.

### 4.2 Improve error messages for common failures
**File:** `src/pages/Demo.tsx:195-244`
**Fix:** Add specific error messages for:
- Screenshot capture timeout → "This site is taking too long to load. Try a simpler page."
- AI extraction failure → "We couldn't analyze this page. It may be behind a login wall."
- Rate limit → Show time remaining until reset

### 4.3 Fix email popup timing
**File:** `src/pages/Demo.tsx:597-602`
**Problem:** Popup appears 3 seconds after generation, potentially blocking the user from seeing results.
**Fix:** Delay to 8 seconds or trigger on scroll past the preview image.

---

## Phase 5: Reliability & Performance

### 5.1 Add circuit breaker for screenshot capture
**Problem:** Slow sites can hang the entire generation pipeline.
**Fix:** Add a hard 15-second timeout for screenshot capture with immediate fallback to HTML-only extraction.

### 5.2 Fix quality gate thresholds
**File:** `backend/services/quality_gates.py`
**Problem:** Thresholds (0.65 min extraction, 0.55 min AI confidence) are too strict and cause unnecessary fallbacks.
**Fix:** Lower to 0.50/0.40 respectively - a mediocre but correct preview is better than a fallback.

### 5.3 Reduce redundant AI calls
**Problem:** Multiple agents (Visual Analyst, Content Curator, Design Archaeologist, Quality Critic) all run in parallel even for simple pages, wasting time and money.
**Fix:** For demo mode, run only the Content Curator + a simplified visual analysis. Reserve full multi-agent orchestration for SaaS tier.

---

## Implementation Order (Priority)

1. **Phase 1** (Critical bugs) - Must fix first, everything else depends on these working
2. **Phase 2.1-2.4** (Image quality) - Highest visual impact
3. **Phase 3.1-3.2** (AI extraction + colors) - Content quality
4. **Phase 4.1-4.3** (Frontend UX) - User experience
5. **Phase 2.5, 3.3-3.4, 5.1-5.3** (Polish) - Refinement

## Estimated Scope
- ~15 files modified
- ~800 lines changed
- Core changes in: `preview_image_generator.py`, `preview_engine.py`, `preview_reasoning.py`, `brand_extractor.py`, `Demo.tsx`
