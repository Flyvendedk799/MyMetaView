# AI Quality Improvement: Implementation Guide

## Overview

This document provides specific implementation steps to improve the AI's quality and universal applicability.

## Core Changes

### 1. Rewrite STAGE_1_2_3_PROMPT

**Location**: `backend/services/preview_reasoning.py` (line ~252)

**Current Issues**:
- Too marketing-focused ("IRRESISTIBLE", "PERFECT")
- Overly prescriptive ("THE ONE RULE")
- Assumes conversion intent
- Too many specific rules for different page types

**New Approach**:
```python
STAGE_1_2_3_PROMPT = """You are an expert web content analyzer extracting accurate information from webpages.

MISSION: Extract the most important and accurate content from this page to create a preview that accurately represents what users will find.

=== EXTRACTION PRINCIPLES ===
1. **Accuracy First**: Extract EXACT text as it appears on the page - no paraphrasing or "improvements"
2. **Completeness**: Extract the primary title, description, and most relevant visual element
3. **Relevance**: Focus on the main content, ignore navigation, footers, and boilerplate
4. **Neutrality**: Extract what's there, not what "should" be there for marketing purposes

=== WHAT TO EXTRACT ===

1. **PRIMARY TITLE** (the main heading or page name)
   - Look for: H1 tags, page title, og:title, main headline
   - For profile pages: Person's name (if clearly a personal profile)
   - For product pages: Product name
   - For articles: Article title
   - For company pages: Company name or main value proposition
   - Preserve exact wording - don't rewrite or "improve"

2. **DESCRIPTION** (what the page is about)
   - Look for: Meta description, og:description, main paragraph, hero text
   - Extract 1-2 sentences that describe the page content
   - Focus on factual information, not marketing claims
   - If no description available, use the first meaningful paragraph

3. **VISUAL ELEMENT** (most relevant image)
   - Look for: og:image, hero image, logo, product image, profile photo
   - Prioritize images that represent the page content
   - For profiles: Profile photo/avatar
   - For products: Product image
   - For companies: Logo or hero image

4. **SUPPORTING INFORMATION** (if available and relevant)
   - Ratings/reviews (with numbers if available)
   - Key facts or statistics
   - Location or contact information
   - Pricing (for product pages)
   - Author/byline (for articles)

=== PAGE TYPE CLASSIFICATION ===

Classify the page type based on content, not marketing intent:
- **profile**: Personal profile page (one person)
- **product**: Product or service page (with pricing/details)
- **article**: Blog post, news article, documentation
- **company**: Company homepage, about page, landing page
- **service**: Service offering page
- **portfolio**: Portfolio or showcase page
- **unknown**: Can't determine clearly

Use these signals:
- URL patterns (/profile/, /product/, /blog/, /about/)
- Content structure (pricing tables → product, team page → company)
- Visual elements (profile photo → profile, product images → product)

=== WHAT TO IGNORE ===
- Navigation menus and links
- Footer content
- Cookie notices and legal text
- Social media share buttons
- Generic stock photos
- Boilerplate text ("Welcome", "About Us" without context)

=== OUTPUT FORMAT ===

Return JSON with this structure:
{{
    "page_type": "<profile|product|article|company|service|portfolio|unknown>",
    "primary_title": "<exact title text from page>",
    "description": "<description text, preserve original wording>",
    "supporting_info": {{
        "rating": "<rating if available, e.g., '4.5★ (120 reviews)'>",
        "key_facts": ["<fact 1>", "<fact 2>"],
        "location": "<location if relevant>",
        "pricing": "<price if product page>"
    }},
    "visual_elements": [
        {{
            "type": "<logo|hero|product|profile|other>",
            "bbox": {{"x": 0.0-1.0, "y": 0.0-1.0, "width": 0.0-1.0, "height": 0.0-1.0}},
            "description": "<what this image shows>"
        }}
    ],
    "color_palette": {{
        "primary": "<hex color from page>",
        "secondary": "<hex color>",
        "accent": "<hex color>"
    }},
    "confidence": <0.0-1.0>
}}

=== CRITICAL RULES ===
1. EXACT TEXT ONLY - No paraphrasing, no "improving" the copy
2. FACTUAL OVER MARKETING - Extract facts, not sales pitches
3. COMPLETE OVER PERFECT - Better to have complete info than "perfect" marketing copy
4. PRESERVE ORIGINAL - Keep original wording, capitalization, punctuation
5. NEUTRAL TONE - Don't add excitement or urgency that isn't there
"""
```

### 2. Simplify STAGE_4_5_PROMPT

**Location**: `backend/services/preview_reasoning.py` (line ~705)

**Current Issues**:
- Too focused on conversion ("1.5 seconds to convince")
- Assumes marketing intent
- Overly complex layout decisions

**New Approach**:
```python
STAGE_4_5_PROMPT = """You're creating a preview card that accurately represents the webpage content.

EXTRACTED CONTENT:
{regions_json}

PAGE TYPE: {page_type}
COLORS: Primary={primary}, Secondary={secondary}, Accent={accent}

=== LAYOUT DECISIONS ===

Create a clean, readable preview that includes:
1. **Title** - The primary heading (required)
2. **Description** - What the page is about (required if available)
3. **Visual** - Most relevant image (logo, hero, or product image)
4. **Supporting Info** - Ratings, facts, or other relevant details (optional)

=== DECISION FRAMEWORK ===

For each extracted element, decide:
- **Include**: Essential information that helps users understand the page
- **Exclude**: Navigation, boilerplate, or redundant information

Prioritize:
1. Accuracy - Content must accurately represent the page
2. Clarity - Users should understand what the page is about
3. Completeness - Include all important information

=== OUTPUT FORMAT ===

{{
    "layout": {{
        "template_type": "<profile|product|article|company|service|portfolio|landing>",
        "title": "<region_id for title>",
        "description": "<region_id for description>",
        "visual": "<region_id for main image>",
        "supporting": ["<region_id 1>", "<region_id 2>"]
    }},
    "reasoning": "<brief explanation of layout choices>"
}}
"""
```

### 3. Improve HTML Metadata Integration

**Location**: `backend/services/preview_engine.py`

**Changes**:
- Prioritize HTML metadata over AI extraction
- Use AI as enhancement, not primary source
- Better fallback when HTML is insufficient

**Implementation**:
```python
def _enhance_ai_result_with_html(self, result, html_content: str):
    """Enhanced HTML integration - HTML as primary source, AI as enhancement."""
    metadata = extract_metadata_from_html(html_content)
    semantic = extract_semantic_structure(html_content)
    
    # PRIORITY 1: Use HTML metadata (most reliable)
    html_title = (
        metadata.get("og_title") or
        metadata.get("priority_title") or
        metadata.get("twitter_title") or
        metadata.get("title") or
        None
    )
    
    html_description = (
        metadata.get("og_description") or
        metadata.get("priority_description") or
        metadata.get("twitter_description") or
        metadata.get("description") or
        None
    )
    
    # PRIORITY 2: Use AI extraction if HTML is insufficient
    ai_title = result.title or ""
    ai_description = result.description or ""
    
    # Choose best title (HTML preferred, AI as fallback)
    if html_title and len(html_title.strip()) > 5:
        # Validate HTML title is better than AI title
        if not ai_title or len(html_title) > len(ai_title) * 0.8:
            result.title = html_title
    elif ai_title and len(ai_title.strip()) > 5:
        result.title = ai_title
    else:
        # Fallback: use domain name
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        result.title = parsed.netloc.replace('www.', '').replace('.', ' ').title()
    
    # Choose best description (HTML preferred, AI as fallback)
    if html_description and len(html_description.strip()) > 20:
        result.description = html_description[:300]
    elif ai_description and len(ai_description.strip()) > 20:
        result.description = ai_description[:300]
    else:
        # Try semantic extraction
        primary_content = semantic.get("primary_content", "")
        if primary_content:
            result.description = primary_content[:300]
    
    # Enhance tags from HTML if missing
    if not result.tags or len(result.tags) < 2:
        keywords = semantic.get("topic_keywords", []) or metadata.get("keywords", "").split(",")
        if keywords:
            clean_keywords = [k.strip() for k in keywords if k.strip() and len(k.strip()) > 2][:5]
            if clean_keywords:
                result.tags = clean_keywords
    
    return result
```

### 4. Simplify Page Type Classification

**Location**: `backend/services/preview_engine.py`

**Changes**:
- Use URL patterns + HTML structure
- Less AI-driven classification
- More deterministic

**Implementation**:
```python
def _classify_page_type(self, url: str, html_content: str) -> str:
    """Classify page type using URL patterns and HTML structure."""
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # URL-based classification (most reliable)
    if '/profile/' in path or '/@' in path or '/user/' in path:
        return "profile"
    elif '/product/' in path or '/shop/' in path or '/store/' in path or '/buy/' in path:
        return "product"
    elif '/blog/' in path or '/post/' in path or '/article/' in path or '/news/' in path:
        return "article"
    elif '/service/' in path or '/services/' in path:
        return "service"
    elif '/portfolio/' in path or '/work/' in path:
        return "portfolio"
    
    # HTML structure-based classification
    metadata = extract_metadata_from_html(html_content)
    
    # Check for product indicators
    if metadata.get("product_price") or metadata.get("availability"):
        return "product"
    
    # Check for article indicators
    if metadata.get("article_published") or metadata.get("article_author"):
        return "article"
    
    # Default to company/landing for business pages
    return "company"
```

### 5. Improve Quality Validation

**Location**: `backend/services/preview_engine.py`

**Changes**:
- Better validation logic
- Focus on completeness and accuracy
- Clear quality scores

**Implementation**:
```python
def _validate_result_quality(self, result: PreviewEngineResult, url: str) -> PreviewEngineResult:
    """Validate preview quality - focus on completeness and accuracy."""
    
    quality_issues = []
    
    # Title validation
    if not result.title or len(result.title.strip()) < 3:
        quality_issues.append("Title is missing or too short")
        # Try to extract from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        result.title = domain.replace('.', ' ').title()
    
    # Description validation
    if not result.description or len(result.description.strip()) < 10:
        quality_issues.append("Description is missing or too short")
        # Try to create basic description
        if result.title:
            result.description = f"Learn more about {result.title}"
    
    # Image validation
    if not result.primary_image_base64 and not result.screenshot_url:
        quality_issues.append("No image available")
    
    # Quality score based on completeness
    completeness_score = 1.0
    if not result.title:
        completeness_score -= 0.3
    if not result.description:
        completeness_score -= 0.3
    if not result.primary_image_base64 and not result.screenshot_url:
        completeness_score -= 0.2
    if not result.tags:
        completeness_score -= 0.1
    if quality_issues:
        completeness_score -= 0.1
    
    result.quality_scores["completeness"] = max(0.0, completeness_score)
    
    if quality_issues:
        result.warnings.extend(quality_issues)
    
    return result
```

## Testing Strategy

### Test Cases

1. **Diverse Business Types**
   - SaaS companies
   - E-commerce stores
   - Professional services
   - Non-profits
   - Educational institutions
   - Personal portfolios
   - Blogs/articles

2. **Edge Cases**
   - Pages with minimal content
   - Pages with no images
   - Pages with broken HTML
   - International pages (non-English)
   - Very long titles/descriptions

3. **Quality Checks**
   - Accuracy: Extracted content matches page
   - Completeness: All fields populated
   - Relevance: Content is appropriate
   - Consistency: Similar pages produce similar results

## Rollout Plan

1. **Week 1**: Implement new prompts (behind feature flag)
2. **Week 2**: A/B test new vs old prompts
3. **Week 3**: Analyze results and refine
4. **Week 4**: Gradual rollout (10% → 50% → 100%)
5. **Week 5**: Monitor and adjust

## Success Criteria

- **Quality**: 90%+ of previews have complete, accurate content
- **Applicability**: Works for 95%+ of business types
- **Consistency**: Similar pages produce similar results
- **User Satisfaction**: Users find previews accurate and useful
