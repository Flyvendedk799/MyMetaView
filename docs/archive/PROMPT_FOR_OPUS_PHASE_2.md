# Preview Engine Upgrade - Phase 2: Deep Integration & Polish

## Context

You are analyzing a SaaS application that generates branded URL previews (Open Graph images). The system has recently undergone a **7-phase upgrade** that introduced major new capabilities. Your mission is to **deeply integrate** these new components, **fix integration gaps**, and **polish the system** to production excellence.

## Current System State (Post Phase 1 Upgrade)

The following components were added in the first upgrade phase:

### New Components Created

1. **`backend/services/brand_extractor.py`** - AI-Powered Logo Detection
   - `extract_logo_with_ai()` - GPT-4o vision for logo bounding boxes
   - `crop_logo_from_screenshot()` - Crops logos from screenshots
   - Integration: Called from `extract_brand_logo()` as priority 1

2. **`backend/services/content_sanitizer.py`** - Cookie/Nav Filtering
   - `sanitize_html_for_extraction()` - Pre-extraction HTML cleaning
   - `sanitize_extracted_content()` - Post-extraction validation
   - Pattern libraries for cookies, nav, footer, popups
   - Integration: Called from `MultiModalFusionEngine`

3. **`backend/services/composition_intelligence.py`** - Layout Selection
   - `CompositionIntelligence` class with content analysis
   - `select_optimal_composition()` - Scores and selects best layout
   - `score_visual_balance()` - Validates visual balance
   - **ISSUE: Created but NOT fully integrated into rendering pipeline**

4. **`backend/services/font_manager.py`** - Font Intelligence
   - `FONT_PERSONALITY_MAP` - Maps personalities to fonts
   - `FontManager` class with system font discovery
   - `get_fonts_for_personality()` - Returns typography sets
   - **ISSUE: Font downloading/caching not implemented**

### Enhanced Components

5. **`backend/services/adaptive_template_engine.py`**
   - `TYPOGRAPHY_PERSONALITY_MAP` - Typography settings per personality
   - `apply_dna_visual_effects()` - Full visual effects application
   - `_apply_spatial_intelligence()` - Density/rhythm adjustments
   - Enhanced `_render_headline()` with full DNA application

6. **`backend/services/quality_orchestrator.py`**
   - `QualityTier` enum (PREMIUM/STANDARD/ACCEPTABLE/RETRY/FALLBACK)
   - Graduated gate enforcement
   - `get_smart_fallback_colors()` - Brand-aware fallbacks
   - `get_tier_specific_enhancements()` - Tier-based actions

7. **`backend/services/preview_image_generator.py`**
   - `smart_truncate()` - Sentence/word boundary truncation
   - Enhanced `_wrap_text()` with smart truncation

8. **`backend/services/preview_reasoning.py`**
   - `ABSOLUTE EXCLUSIONS` added to AI prompts
   - `smart_truncate_text()` for content refinement

9. **`backend/services/multi_modal_fusion.py`**
   - Pre-extraction HTML sanitization
   - Post-extraction content validation

---

## Known Integration Gaps

### Critical Gaps

1. **CompositionIntelligence Not Used in Rendering**
   - `composition_intelligence.py` was created but `AdaptiveTemplateEngine` doesn't use it
   - Composition selection is still hardcoded based on design style only
   - The dynamic zone adjustments from `CompositionDecision` aren't applied

2. **FontManager Not Fully Integrated**
   - Font downloading from Google Fonts not implemented
   - Only system fonts are discovered
   - `load_pillow_font()` only partially uses FontManager

3. **Quality Tier Actions Not Executed**
   - `QualityOrchestrator.get_tier_specific_enhancements()` returns actions but nothing executes them
   - `recommended_action` from `UnifiedQualityMetrics` not used in pipeline

4. **Preview Engine Doesn't Use New Components**
   - `preview_engine.py` doesn't call `CompositionIntelligence`
   - Quality tier decisions don't trigger enhancements
   - Fallback doesn't use `get_smart_fallback_colors()`

### Missing Features

5. **No Visual Quality Validation**
   - Generated images aren't validated for visual quality
   - No contrast checking, text readability validation
   - No compositional balance scoring after render

6. **No A/B Testing Infrastructure**
   - Can't compare old vs new preview quality
   - No metrics collection for quality improvement

7. **Incomplete Error Recovery**
   - When AI logo detection fails, recovery path is basic
   - Content sanitizer failures don't have graceful degradation

---

## Your Mission

Transform this partially-integrated system into a **seamlessly unified preview generation engine** where all components work together flawlessly.

### Primary Goals

1. **Deep Integration**: Wire all new components into the main pipeline
2. **Execute Quality Actions**: Make quality tier decisions trigger real improvements
3. **Visual Validation**: Add post-render quality checks
4. **Robust Fallbacks**: Ensure graceful degradation at every stage
5. **Performance**: Maintain <5s generation time despite new features

### Success Criteria

| Metric | Current (Est.) | Target |
|--------|----------------|--------|
| Logo Detection Rate | ~60% | 90% |
| Design Fidelity | ~0.55 | 0.80 |
| Cookie Leakage | ~5% | <1% |
| Fallback Rate | ~20% | <8% |
| Quality Score | ~0.65 | 0.85 |
| P95 Latency | ~6s | <5s |

---

## Deliverables

### 1. Integration Architecture Document

Map exactly how each component should connect:
```
preview_engine.py
├── brand_extractor.py (AI logo) ✓ Integrated
├── content_sanitizer.py ✓ Integrated via multi_modal_fusion
├── multi_modal_fusion.py ✓ Uses sanitizer
├── composition_intelligence.py ❌ NOT INTEGRATED
├── adaptive_template_engine.py
│   ├── font_manager.py ⚠️ Partial
│   └── composition_intelligence.py ❌ NOT USED
└── quality_orchestrator.py
    └── tier actions ❌ NOT EXECUTED
```

### 2. Integration Implementations

#### A. CompositionIntelligence → AdaptiveTemplateEngine
- Use `select_optimal_composition()` in template engine init
- Apply `CompositionDecision.zone_adjustments` to layout zones
- Apply multipliers (font_size, padding, spacing)
- Respect feature flags (show_logo, show_accent_bar, etc.)

#### B. Quality Tier → Action Execution
- In `preview_engine.py`, after quality assessment:
  - If ACCEPTABLE: Apply minor enhancements
  - If RETRY: Re-run extraction with different params
  - If FALLBACK: Use `get_smart_fallback_colors()`
- Implement the actual enhancement functions

#### C. FontManager → Full Integration
- Complete font downloading from Google Fonts
- Add font caching with TTL
- Use FontManager in ALL font loading (not just headline)
- Typography validation before render

### 3. Visual Quality Validator

Create `backend/services/visual_quality_validator.py`:
- Validate rendered image contrast ratios
- Check text is readable (WCAG AA/AAA)
- Verify logo is visible and not cropped
- Score compositional balance
- Detect rendering artifacts

### 4. Enhanced Error Recovery

For each component, implement:
- Timeout handling
- Graceful degradation
- Fallback chain
- Error logging with context

### 5. Pipeline Orchestration

Update `preview_engine.py` to:
```python
# 1. Capture & Sanitize
screenshot, html = capture_page(url)
sanitized_html = sanitize_html(html)

# 2. Extract with Intelligence
brand = extract_brand_with_ai_logo(html, screenshot)
content = extract_content(sanitized_html, screenshot)
design_dna = extract_design_dna(screenshot)

# 3. Select Composition
composition = select_optimal_composition(content, design_dna, page_type)

# 4. Generate with Full DNA
preview_image = generate_with_composition(
    content, 
    design_dna, 
    composition,
    font_manager.get_typography(design_dna.typography.headline_personality)
)

# 5. Validate Quality
quality = assess_quality(preview_image, design_dna)

# 6. Execute Tier Actions
if quality.tier == RETRY:
    # Re-extract and regenerate
elif quality.tier == FALLBACK:
    preview_image = generate_smart_fallback(brand.colors)
elif quality.tier == ACCEPTABLE:
    # Apply minor enhancements

# 7. Visual Validation
visual_quality = validate_visual_quality(preview_image)

# 8. Return with Metrics
return PreviewResult(
    image=preview_image,
    quality_scores=quality,
    visual_scores=visual_quality
)
```

---

## Key Files to Analyze

Read these files to understand current state:

1. `backend/services/preview_engine.py` - Main orchestration
2. `backend/services/adaptive_template_engine.py` - Image generation
3. `backend/services/composition_intelligence.py` - Layout selection (NEW)
4. `backend/services/font_manager.py` - Font management (NEW)
5. `backend/services/quality_orchestrator.py` - Quality tiers (ENHANCED)
6. `backend/services/preview_image_generator.py` - Legacy generator
7. `backend/services/multi_modal_fusion.py` - Content extraction (ENHANCED)

---

## Constraints

1. **Backward Compatibility**: Existing API must work unchanged
2. **OpenAI GPT-4o**: Continue using for AI features
3. **Image Size**: 1200x630px OG images
4. **Latency**: P95 < 5 seconds
5. **Error Rate**: < 1% hard failures
6. **No New Dependencies**: Use existing packages only

---

## Output Format

Provide your implementation as:

1. **Gap Analysis**: Detailed breakdown of each integration gap
2. **Implementation Plan**: Phase-by-phase with dependencies
3. **Code Changes**: Actual code modifications for each integration
4. **Testing Strategy**: How to validate each integration works
5. **Rollback Plan**: How to disable new features if issues arise

---

## Questions to Answer

1. How should `CompositionIntelligence` integrate with `AdaptiveTemplateEngine`?
2. What's the execution flow for quality tier actions?
3. How do we validate visual quality programmatically?
4. Where should font downloading happen (startup vs lazy)?
5. How do we measure if integrations improved quality?

---

## Start Here

Begin by reading the key files listed above, then:
1. Map the current data flow through the pipeline
2. Identify exact integration points for each new component
3. Propose the integration architecture
4. Implement changes phase by phase
5. Validate each phase works before moving to next

