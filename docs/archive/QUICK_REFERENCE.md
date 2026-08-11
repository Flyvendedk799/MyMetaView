# AI Quality Improvement - Quick Reference

## The Problem
Current AI is **too gimmicky** - assumes all pages need marketing language ("hooks", "social proof", conversion copywriting). Doesn't work for informational, educational, or non-commercial pages.

## The Solution
**Make AI neutral, accurate, and universally applicable** by:
1. Removing marketing language from prompts
2. Prioritizing HTML metadata over AI extraction
3. Simplifying page classification
4. Focusing on accuracy over conversion

## Key Changes

| Area | Before | After |
|------|--------|-------|
| **Language** | "IRRESISTIBLE", "PERFECT", conversion-focused | Neutral, factual, information-focused |
| **Primary Source** | AI vision analysis | HTML metadata (og:title, og:description) |
| **Page Classification** | Complex AI-driven rules | Simple URL patterns + HTML structure |
| **Content Focus** | What "should" be there | What's actually there |
| **Tone** | Marketing/sales | Informative/accurate |

## Files to Modify

1. **`backend/services/preview_reasoning.py`**
   - Rewrite `STAGE_1_2_3_PROMPT` (line ~252)
   - Simplify `STAGE_4_5_PROMPT` (line ~705)
   - Remove marketing language

2. **`backend/services/preview_engine.py`**
   - Improve `_enhance_ai_result_with_html()` method
   - Prioritize HTML metadata
   - Add quality validation

3. **`backend/services/metadata_extractor.py`**
   - Ensure robust HTML extraction
   - Better fallbacks

## Implementation Timeline

- **Week 1**: Rewrite prompts (behind feature flag)
- **Week 2**: Improve HTML integration
- **Week 3**: Simplify layout generation
- **Week 4**: Add quality validation
- **Week 5**: Test and refine

## Success Metrics

- ✅ 90%+ previews have complete, accurate content
- ✅ Works for 95%+ of business types
- ✅ Users find previews accurate and useful
- ✅ Less "gimmicky" language

## Risk Mitigation

- Gradual rollout (10% → 50% → 100%)
- A/B testing new vs old prompts
- Monitor quality metrics
- Keep old prompts as fallback

## Example Transformation

**Before**: "Transform Your Business with Our Expert Services - Join 10,000+ satisfied clients!"

**After**: "Smith & Associates - Legal Services. Providing legal services for businesses and individuals since 1995."

## Next Steps

1. Review plan documents
2. Start with prompt rewrites
3. Test incrementally
4. Monitor and adjust

---

**Core Principle**: Extract what's actually on the page accurately, don't try to optimize for conversion. This makes it work for ALL businesses.
