# AI Quality Improvement Summary

## The Problem

The current preview engine is **too gimmicky and marketing-focused**, making it less applicable for all businesses. It assumes every page needs "hooks", "social proof", and conversion copywriting, which doesn't work for:
- Informational pages
- Educational content
- Non-profit organizations
- Professional services
- Documentation sites
- And many other business types

## The Solution

**Make the AI more neutral, accurate, and universally applicable** by:

1. **Removing marketing language** - Focus on accurate extraction, not conversion optimization
2. **Simplifying prompts** - Fewer rules, clearer principles
3. **Prioritizing HTML metadata** - Use AI as enhancement, not primary source
4. **Improving quality** - Better validation and completeness checks

## Key Changes

### 1. Rewrite Core Prompts
- **Before**: "Extract content that makes this preview IRRESISTIBLE"
- **After**: "Extract the most important and accurate content from this page"

### 2. Simplify Page Classification
- **Before**: Complex profile vs company detection with many rules
- **After**: Simple URL pattern + HTML structure analysis

### 3. Improve HTML Integration
- **Before**: AI vision as primary source
- **After**: HTML metadata as primary, AI as enhancement

### 4. Better Quality Validation
- **Before**: Focus on conversion potential
- **After**: Focus on completeness and accuracy

## Implementation Steps

1. **Week 1**: Rewrite prompts with neutral language
2. **Week 2**: Improve HTML metadata integration
3. **Week 3**: Simplify layout generation
4. **Week 4**: Add quality validation
5. **Week 5**: Test and refine

## Expected Outcomes

✅ **More Universal**: Works for all business types
✅ **More Accurate**: Extracted content matches page content
✅ **Less Gimmicky**: No marketing language or conversion focus
✅ **Better Quality**: More complete and reliable previews

## Files to Modify

1. `backend/services/preview_reasoning.py` - Core prompts
2. `backend/services/preview_engine.py` - HTML integration and validation
3. `backend/services/metadata_extractor.py` - Better HTML extraction

## Risk Mitigation

- **Gradual Rollout**: Implement behind feature flag
- **A/B Testing**: Test new vs old prompts
- **Monitoring**: Track quality metrics closely
- **Rollback Plan**: Keep old prompts as fallback

## Success Metrics

- **Quality**: 90%+ of previews have complete, accurate content
- **Applicability**: Works for 95%+ of business types
- **User Satisfaction**: Users find previews accurate and useful

## Next Steps

1. Review and approve this plan
2. Start with prompt rewrites (Week 1)
3. Test incrementally
4. Monitor and adjust

---

**Bottom Line**: Make the AI extract what's actually on the page accurately, rather than trying to optimize for conversion. This will make it work for ALL businesses, not just marketing-focused ones.
