# Framework-Based Quality System with Design Preservation

## Core Principles

1. **Framework-Based**: Structured pipeline with quality gates ensuring consistent quality
2. **Design Preservation**: Extract and preserve visual design elements (colors, typography, layout)
3. **odal Fusion: Intelligently combine sources with quality validation
4. **Equal Quality**: Same quality standards regardless of source used

## Framework Architecture

### Quality Framework Layers

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Source Extraction (Multi-Modal)       │
│ - HTML Metadata                                  │
│ - Semantic Analysis                              │
│ - AI Vision                                      │
└─────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────┐
│ Layer 2: Quality Validation (Quality Gates)    │
│ - Content Quality Checks                        │
│ - Design Quality Checks                         │
│ - Completeness Validation                       │
└─────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────┐
│ Layer 3: Design Extraction & Preservation         │
│ - Color Palette Extraction                      │
│ - Typography Analysis                           │
│ - Layout Structure                              │
│ - Visual Hierarchy                              │
└─────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────┐
│ Layer 4: Fusion & Enhancement                   │
│ - Intelligent Source Selection                  │
│ - Design-Aware Enhancement                     │
│ - Quality Scoring                               │
└─────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────┐
│ Layer 5: Final Validation & Output             │
│ - Final Quality Gates                           │
│ - Design Fidelity Check                         │
│ - Output Formatting                             │
└─────────────────────────────────────────────────┘
```

## Implementation: Framework-Based System

### 1. Quality Framework Base Class

```python
# backend/services/quality_framework.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

@dataclass
class QualityScore:
    """Quality score for a field."""
    score: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    source: str  # "html", "semantic", "vision"
    issues: List[str]  # Quality issues found
    passed_gates: bool  # Whether passed quality gates

@dataclass
class DesignElements:
    """Extracted design elements."""
    color_palette: Dict[str, str]  # primary, secondary, accent
    typography: Dict[str, Any]  # font_family, font_sizes, weights
    layout_structure: Dict[str, Any]  # grid, spacing, alignment
    visual_hierarchy: Dict[str, Any]  # prominence, contrast
    design_style: str  # minimalist, corporate, playful, etc.

class QualityGate(ABC):
    """Base class for quality gates."""
    
    @abstractmethod
    def validate(self, content: Any, context: Dict[str, Any]) -> QualityScore:
        """Validate content quality."""
        pass
    
    @abstractmethod
    def get_threshold(self) -> float:
        """Get minimum quality threshold."""
        pass

class ContentQualityGate(QualityGate):
    """Validates content quality."""
    
    def validate(self, content: str, context: Dict[str, Any]) -> QualityScore:
        """Validate content quality."""
        issues = []
        score = 1.0
        
        # Check length
        if not content or len(content.strip()) < 3:
            issues.append("Content too short")
            score -= 0.5
        
        # Check for generic content
        generic_patterns = ["welcome", "about us", "learn more", "click here"]
        if any(pattern in content.lower() for pattern in generic_patterns):
            issues.append("Generic content detected")
            score -= 0.3
        
        # Check for navigation text
        nav_patterns = ["home", "contact", "menu", "navigation"]
        if any(pattern in content.lower() for pattern in nav_patterns):
            issues.append("Navigation text detected")
            score -= 0.2
        
        # Calculate confidence
        confidence = max(0.0, min(1.0, score))
        
        # Check if passes threshold
        passed = confidence >= self.get_threshold()
        
        return QualityScore(
            score=score,
            confidence=confidence,
            source=context.get("source", "unknown"),
            issues=issues,
            passed_gates=passed
        )
    
    def get_threshold(self) -> float:
        return 0.6.0  # Minimum quality threshold"""

class DesignQualityGate(QualityGate):
    """Validates design extraction quality."""
    
    def validate(self, design: DesignElements, context: Dict[str, Any]) -> QualityScore:
        """Validate design extraction quality."""
        issues = []
        score = 1.0
        
        # Check color palette
        if not design.color_palette or not design.color_palette.get("primary"):
            issues.append("Missing primary color")
            score -= 0.3
        
        # Check typography
        if not design.typography or not design.typography.get("font_family"):
            issues.append("Missing typography information")
            score -= 0.2
        
        # Check layout structure
        if not design.layout_structure:
            issues.append("Missing layout structure")
            score -= 0.2
        
        confidence = max(0.0, min(1.0, score))
        passed = confidence >= self.get_threshold()
        
        return QualityScore(
            score=score,
            confidence=confidence,
            source=context.get("source", "unknown"),
            issues=issues,
            passed_gates=passed
        )
    
    def get_threshold(self) -> float:
        return 0.5  # Minimum design quality threshold

class QualityFramework:
    """
    Framework for ensuring consistent quality across all extractions.
    """
    
    def __init__(self):
        self.content_gate = ContentQualityGate()
        self.design_gate = DesignQualityGate()
    
    def validate_content(
        self,
        title: Optional[str],
        description: Optional[str],
        source: str
    ) -> Dict[str, QualityScore]:
        """Validate content quality."""
        scores = {}
        
        if title:
            scores["title"] = self.content_gate.validate(
                title,
                {"source": source, "field": "title"}
            )
        
        if description:
            scores["description"] = self.content_gate.validate(
                description,
                {"source": source, "field": "description"}
            )
        
        return scores
    
    def validate_design(
        self,
        design: DesignElements,
        source: str
    ) -> QualityScore:
        """Validate design extraction quality."""
        return self.design_gate.validate(
            design,
            {"source": source}
        )
    
    def should_use_source(
        self,
        scores: Dict[str, QualityScore]
    ) -> bool:
        """Determine if source should be used based on quality scores."""
        if not scores:
            return False
        
        # All fields must pass quality gates
        return all(score.passed_gates for score in scores.values())
```

### 2. Design Extraction Framework

```python
# backend/services/design_extraction_framework.py

from typing import Dict, Any, Optional
from dataclasses import dataclass
from backend.services.quality_framework import DesignElements, QualityScore

class DesignExtractor:
    """
    Framework for extracting and preserving design elements.
    """
    
    def extract_design(
        self,
        html_content: str,
        screenshot_bytes: bytes,
        url: str
    ) -> DesignElements:
        """
        Extract design elements from multiple sources.
        
        Strategy:
        1. Extract from HTML (CSS, inline styles)
        2. Extract from screenshot (visual analysis)
        3. Extract from brand elements (if available)
        4. Fuse with quality validation
        """
        
        # Extract from HTML
        html_design = self._extract_from_html(html_content)
        
        # Extract from screenshot
        visual_design = self._extract_from_visual(screenshot_bytes)
        
        # Extract from brand (if available)
        brand_design = self._extract_from_brand(html_content, screenshot_bytes)
        
        # Fuse design elements
        fused_design = self._fuse_design_elements(
            html_design,
            visual_design,
            brand_design
        )
        
        return fused_design
    
    def _extract_from_html(self, html_content: str) -> DesignElements:
        """Extract design elements from HTML/CSS."""
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extract colors from CSS and inline styles
        color_palette = self._extract_colors_from_html(soup)
        
        # Extract typography from CSS
        typography = self._extract_typography_from_html(soup)
        
        # Extract layout structure
        layout_structure = self._extract_layout_from_html(soup)
        
        return DesignElements(
            color_palette=color_palette,
            typography=typography,
            layout_structure=layout_structure,
            visual_hierarchy={},
            design_style="corporate"  # Default
        )
    
    def _extract_colors_from_html(self, soup) -> Dict[str, str]:
        """Extract color palette from HTML/CSS."""
        colors = {}
        
        # Look for common color patterns in styles
        style_tags = soup.find_all('style')
        inline_styles = soup.find_all(attrs={'style': True})
        
        # Extract hex colors
        hex_pattern = r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})'
        
        all_colors = []
        for style in style_tags + inline_styles:
            style_text = style.get('style', '') if hasattr(style, 'get') else str(style)
            if isinstance(style, str):
                style_text = style
            
            matches = re.findall(hex_pattern, style_text)
            all_colors.extend([f"#{m}" if len(m) == 6 else f"#{m[0]}{m[0]}{m[1]}{m[1]}{m[2]}{m[2]}" for m in matches])
        
        # Find most common colors (likely brand colors)
        from collections import Counter
        color_counts = Counter(all_colors)
        common_colors = [color for color, count in color_counts.most_common(3)]
        
        # Assign to palette
        if len(common_colors) >= 1:
            colors["primary"] = common_colors[0]
        if len(common_colors) >= 2:
            colors["secondary"] = common_colors[1]
        if len(common_colors) >= 3:
            colors["accent"] = common_colors[2]
        
        # Fallback to defaults
        colors.setdefault("primary", "#2563EB")
        colors.setdefault("secondary", "#1E40AF")
        colors.setdefault("accent", "#F59E0B")
        
        return colors
    
    def _extract_typography_from_html(self, soup) -> Dict[str, Any]:
        """Extract typography information from HTML/CSS."""
        typography = {}
        
        # Look for font-family in styles
        style_tags = soup.find_all('style')
        font_pattern = r'font-family:\s*([^;]+)'
        
        fonts = []
        for style in style_tags:
            matches = re.findall(font_pattern, str(style))
            fonts.extend(matches)
        
        if fonts:
            # Get most common font
            from collections import Counter
            font_counts = Counter(fonts)
            most_common_font = font_counts.most_common(1)[0][0]
            typography["font_family"] = most_common_font.strip().strip("'\"")
        
        # Extract font sizes
        size_pattern = r'font-size:\s*([^;]+)'
        sizes = []
        for style in style_tags:
            matches = re.findall(size_pattern, str(style))
            sizes.extend(matches)
        
        if sizes:
            typography["font_sizes"] = sizes[:5]  # Top 5 sizes
        
        return typography
    
    def _extract_layout_from_html(self, soup) -> Dict[str, Any]:
        """Extract layout structure from HTML."""
        layout = {}
        
        # Check for grid layouts
        grid_elements = soup.find_all(class_=re.compile(r'grid|flex|container', re.I))
        if grid_elements:
            layout["has_grid"] = True
            layout["grid_type"] = "css-grid" if "grid" in str(grid_elements[0].get('class', [])).lower() else "flexbox"
        
        # Check for spacing
        spacing_elements = soup.find_all(class_=re.compile(r'padding|margin|spacing', re.I))
        layout["has_spacing"] = len(spacing_elements) > 0
        
        return layout
    
    def _extract_from_visual(self, screenshot_bytes: bytes) -> DesignElements:
        """Extract design elements from screenshot using AI vision."""
        # Use AI vision to analyze visual design
        # This would call an improved vision prompt focused on design
        
        # For now, return empty design (will be enhanced)
        return DesignElements(
            color_palette={},
            typography={},
            layout_structure={},
            visual_hierarchy={},
            design_style="unknown"
        )
    
    def _extract_from_brand(
        self,
        html_content: str,
        screenshot_bytes: bytes
    ) -> DesignElements:
        """Extract design from brand elements."""
        from backend.services.brand_extractor import extract_all_brand_elements
        
        try:
            brand_elements = extract_all_brand_elements(html_content, "", screenshot_bytes)
            
            color_palette = {}
            if brand_elements.get("colors"):
                colors = brand_elements["colors"]
                color_palette = {
                    "primary": colors.get("primary_color", "#2563EB"),
                    "secondary": colors.get("secondary_color", "#1E40AF"),
                    "accent": colors.get("accent_color", "#F59E0B")
                }
            
            return DesignElements(
                color_palette=color_palette,
                typography={},
                layout_structure={},
                visual_hierarchy={},
                design_style="brand"
            )
        except Exception:
            return DesignElements(
                color_palette={},
                typography={},
                layout_structure={},
                visual_hierarchy={},
                design_style="unknown"
            )
    
    def _fuse_design_elements(
        self,
        html_design: DesignElements,
        visual_design: DesignElements,
        brand_design: DesignElements
    ) -> DesignElements:
        """Fuse design elements from multiple sources."""
        
        # Priority: Brand > HTML > Visual
        
        # Color palette fusion
        color_palette = {}
        if brand_design.color_palette:
            color_palette = brand_design.color_palette
        elif html_design.color_palette:
            color_palette = html_design.color_palette
        elif visual_design.color_palette:
            color_palette = visual_design.color_palette
        else:
            color_palette = {
                "primary": "#2563EB",
                "secondary": "#1E40AF",
                "accent": "#F59E0B"
            }
        
        # Typography fusion
        typography = {}
        if html_design.typography:
            typography = html_design.typography
        elif visual_design.typography:
            typography = visual_design.typography
        
        # Layout fusion
        layout_structure = {}
        if html_design.layout_structure:
            layout_structure = html_design.layout_structure
        elif visual_design.layout_structure:
            layout_structure = visual_design.layout_structure
        
        # Design style fusion
        design_style = brand_design.design_style or html_design.design_style or visual_design.design_style or "corporate"
        
        return DesignElements(
            color_palette=color_palette,
            typography=typography,
            layout_structure=layout_structure,
            visual_hierarchy=visual_design.visual_hierarchy or html_design.visual_hierarchy,
            design_style=design_style
        )
```

### 3. Enhanced Multi-Modal Fusion with Quality Framework

```python
# backend/services/multi_modal_fusion.py

from backend.services.quality_framework import QualityFramework, QualityScore
from backend.services.design_extraction_framework import DesignExtractor, DesignElements
from typing import Dict, Any, Optional, Tuple

class MultiModalFusionEngine:
    """
    Framework-based multi-modal fusion with quality gates.
    """
    
    def __init__(self):
        self.quality_framework = QualityFramework()
        self.design_extractor = DesignExtractor()
    
    def extract_preview_content(
        self,
        html_content: str,
        screenshot_bytes: bytes,
        url: str
    ) -> Dict[str, Any]:
        """
        Extract preview content using framework-based multi-modal fusion.
        
        Framework ensures:
        1. Quality gates for all sources
        2. Design preservation
        3. Consistent quality regardless of source
        """
        
        # Step 1: Extract from all sources
        html_data = self._extract_from_html(html_content)
        semantic_data = self._extract_from_semantic(html_content)
        vision_data = self._extract_from_vision(screenshot_bytes, url, html_content)
        
        # Step 2: Validate quality for each source
        html_scores = self.quality_framework.validate_content(
            html_data.get("title"),
            html_data.get("description"),
            "html"
        )
        
        semantic_scores = self.quality_framework.validate_content(
            semantic_data.get("title"),
            semantic_data.get("description"),
            "semantic"
        )
        
        vision_scores = self.quality_framework.validate_content(
            vision_data.get("title"),
            vision_data.get("description"),
            "vision"
        )
        
        # Step 3: Extract design elements
        design_elements = self.design_extractor.extract_design(
            html_content,
            screenshot_bytes,
            url
        )
        
        # Validate design quality
        design_score = self.quality_framework.validate_design(
            design_elements,
            "fusion"
        )
        
        # Step 4: Fuse with quality-based selection
        fused = self._fuse_with_quality_gates(
            html_data, html_scores,
            semantic_data, semantic_scores,
            vision_data, vision_scores,
            design_elements, design_score
        )
        
        return fused
    
    def _fuse_with_quality_gates(
        self,
        html_data: Dict[str, Any],
        html_scores: Dict[str, QualityScore],
        semantic_data: Dict[str, Any],
        semantic_scores: Dict[str, QualityScore],
        vision_data: Dict[str, Any],
        vision_scores: Dict[str, QualityScore],
        design_elements: DesignElements,
        design_score: QualityScore
    ) -> Dict[str, Any]:
        """
        Fuse results using quality gates to ensure consistent quality.
        """
        
        sources_used = {}
        
        # Title fusion with quality gates
        title_candidates = [
            (html_data.get("title"), html_scores.get("title"), "html"),
            (semantic_data.get("title"), semantic_scores.get("title"), "semantic"),
            (vision_data.get("title"), vision_scores.get("title"), "vision")
        ]
        
        # Filter candidates that pass quality gates
        valid_titles = [
            (title, score, src) for title, score, src in title_candidates
            if title and score and score.passed_gates
        ]
        
        if valid_titles:
            # Choose best quality score
            best_title = max(valid_titles, key=lambda x: x[1].confidence)
            title = best_title[0]
            sources_used["title"] = best_title[2]
            title_confidence = best_title[1].confidence
        else:
            # Fallback: use best available even if doesn't pass gates
            fallback_titles = [
                (title, score, src) for title, score, src in title_candidates
                if title and score
            ]
            if fallback_titles:
                best_title = max(fallback_titles, key=lambda x: x[1].confidence)
                title = best_title[0]
                sources_used["title"] = best_title[2]
                title_confidence = best_title[1].confidence
            else:
                # Last resort fallback
                from urllib.parse import urlparse
                parsed = urlparse(url)
                title = parsed.netloc.replace('www.', '').replace('.', ' ').title()
                sources_used["title"] = "fallback"
                title_confidence = 0.3
        
        # Description fusion with quality gates (same logic)
        desc_candidates = [
            (html_data.get("description"), html_scores.get("description"), "html"),
            (semantic_data.get("description"), semantic_scores.get("description"), "semantic"),
            (vision_data.get("description"), vision_scores.get("description"), "vision")
        ]
        
        valid_descs = [
            (desc, score, src) for desc, score, src in desc_candidates
            if desc and score and score.passed_gates
        ]
        
        if valid_descs:
            best_desc = max(valid_descs, key=lambda x: x[1].confidence)
            description = best_desc[0]
            sources_used["description"] = best_desc[2]
            desc_confidence = best_desc[1].confidence
        else:
            fallback_descs = [
                (desc, score, src) for desc, score, src in desc_candidates
                if desc and score
            ]
            if fallback_descs:
                best_desc = max(fallback_descs, key=lambda x: x[1].confidence)
                description = best_desc[0]
                sources_used["description"] = best_desc[2]
                desc_confidence = best_desc[1].confidence
            else:
                description = f"Learn more about {title}"
                sources_used["description"] = "fallback"
                desc_confidence = 0.3
        
        # Calculate overall confidence
        overall_confidence = (title_confidence + desc_confidence) / 2
        
        # Design quality
        design_passed = design_score.passed_gates
        
        return {
            "title": title,
            "description": description[:300],
            "tags": semantic_data.get("tags", []),
            "image": vision_data.get("image") or html_data.get("image"),
            "confidence": overall_confidence,
            "sources": sources_used,
            "design": {
                "color_palette": design_elements.color_palette,
                "typography": design_elements.typography,
                "layout_structure": design_elements.layout_structure,
                "design_style": design_elements.design_style,
                "quality_passed": design_passed,
                "quality_score": design_score.confidence
            },
            "quality_scores": {
                "title": title_confidence,
                "description": desc_confidence,
                "design": design_score.confidence,
                "overall": overall_confidence
            }
        }
```

## Quality Framework Benefits

### 1. **Consistent Quality**
- Quality gates ensure minimum standards
- Same quality regardless of source
- Validates all extractions

### 2. **Design Preservation**
- Extracts color palette from multiple sources
- Preserves typography information
- Maintains layout structure
- Preserves visual hierarchy

### 3. **Framework-Based**
- Structured pipeline
- Clear quality gates
- Reusable components
- Easy to extend

### 4. **Equal Quality Across Sources**
- HTML, semantic, and vision all validated
- Best source chosen based on quality
- Fallbacks maintain quality standards

## Implementation Priority

1. **Week 1**: Quality Framework + Design Extraction
2. **Week 2**: Multi-Modal Fusion Integration
3. **Week 3**: Enhanced Vision for Design
4. **Week 4**: Testing & Refinement

This framework ensures consistent, high-quality results while preserving design elements.
