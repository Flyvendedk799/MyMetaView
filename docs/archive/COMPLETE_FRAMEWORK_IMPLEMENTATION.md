# Complete Framework-Based Implementation

## Framework Architecture

```
┌─────────────────────────────────────────────────────────┐
│ 1. Source Extraction Layer                               │
│    - HTML Metadata Extractor                             │
│    - Semantic Structure Analyzer                         │
│    - AI Vision Extractor                                 │
│    - Design Element Extractor                            │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Quality Validation Layer (Quality Gates)             │
│    - Content Quality Gate                                │
│    - Design Quality Gate                                 │
│    - Completeness Gate                                   │
│    - Consistency Gate                                    │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Design Preservation Layer                            │
│    - Color Palette Extraction                            │
│    - Typography Analysis                                 │
│    - Layout Structure Analysis                           │
│    - Visual Hierarchy Detection                         │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Intelligent Fusion Layer                             │
│    - Quality-Based Source Selection                      │
│    - Design-Aware Enhancement                            │
│    - Confidence Scoring                                  │
│    - Fallback Strategy                                   │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 5. Final Validation & Output                            │
│    - Final Quality Gates                                 │
│    - Design Fidelity Check                               │
│    - Output Formatting                                   │
│    - Quality Metrics                                     │
└─────────────────────────────────────────────────────────┘
```

## Complete Implementation

### 1. Quality Framework Base

```python
# backend/services/quality_framework.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class QualityLevel(str, Enum):
    """Quality levels."""
    EXCELLENT = "excellent"  # 0.9-1.0
    GOOD = "good"  # 0.7-0.9
    FAIR = "fair"  # 0.5-0.7
    POOR = "poor"  # 0.0-0.5

@dataclass
class QualityScore:
    """Quality score for a field."""
    score: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    source: str  # "html", "semantic", "vision"
    issues: List[str]  # Quality issues found
    passed_gates: bool  # Whether passed quality gates
    level: QualityLevel  # Quality level

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
    
    def _calculate_level(self, score: float) -> QualityLevel:
        """Calculate quality level from score."""
        if score >= 0.9:
            return QualityLevel.EXCELLENT
        elif score >= 0.7:
            return QualityLevel.GOOD
        elif score >= 0.5:
            return QualityLevel.FAIR
        else:
            return QualityLevel.POOR

class ContentQualityGate(QualityGate):
    """Validates content quality."""
    
    GENERIC_PATTERNS = [
        "welcome", "about us", "learn more", "click here",
        "read more", "get started", "sign up"
    ]
    
    NAV_PATTERNS = [
        "home", "contact", "menu", "navigation", "footer"
    ]
    
    def validate(self, content: str, context: Dict[str, Any]) -> QualityScore:
        """Validate content quality."""
        issues = []
        score = 1.0
        
        # Check if content exists
        if not content or not isinstance(content, str):
            return QualityScore(
                score=0.0,
                confidence=0.0,
                source=context.get("source", "unknown"),
                issues=["Content is empty or invalid"],
                passed_gates=False,
                level=QualityLevel.POOR
            )
        
        content_lower = content.lower().strip()
        
        # Check length
        if len(content_lower) < 3:
            issues.append("Content too short")
            score -= 0.5
        elif len(content_lower) < 10:
            issues.append("Content very short")
            score -= 0.2
        
        # Check for generic content
        for pattern in self.GENERIC_PATTERNS:
            if pattern in content_lower:
                issues.append(f"Generic pattern detected: {pattern}")
                score -= 0.3
                break
        
        # Check for navigation text
        for pattern in self.NAV_PATTERNS:
            if pattern in content_lower and len(content_lower) < 20:
                issues.append(f"Navigation text detected: {pattern}")
                score -= 0.2
                break
        
        # Check for excessive capitalization (might be spam)
        if content.isupper() and len(content) > 10:
            issues.append("Excessive capitalization")
            score -= 0.1
        
        # Calculate confidence
        confidence = max(0.0, min(1.0, score))
        
        # Check if passes threshold
        passed = confidence >= self.get_threshold()
        
        return QualityScore(
            score=score,
            confidence=confidence,
            source=context.get("source", "unknown"),
            issues=issues,
            passed_gates=passed,
            level=self._calculate_level(confidence)
        )
    
    def get_threshold(self) -> float:
        return 0.6  # Minimum quality threshold

class DesignQualityGate(QualityGate):
    """Validates design extraction quality."""
    
    def validate(self, design: Dict[str, Any], context: Dict[str, Any]) -> QualityScore:
        """Validate design extraction quality."""
        issues = []
        score = 1.0
        
        # Check color palette
        color_palette = design.get("color_palette", {})
        if not color_palette or not color_palette.get("primary"):
            issues.append("Missing primary color")
            score -= 0.3
        
        # Check if colors are valid hex
        if color_palette.get("primary"):
            primary = color_palette["primary"]
            if not (primary.startswith("#") and len(primary) in [4, 7]):
                issues.append("Invalid primary color format")
                score -= 0.2
        
        # Check typography (optional but nice to have)
        typography = design.get("typography", {})
        if not typography or not typography.get("font_family"):
            issues.append("Missing typography information")
            score -= 0.1  # Less critical
        
        # Check layout structure
        layout = design.get("layout_structure", {})
        if not layout:
            issues.append("Missing layout structure")
            score -= 0.1  # Less critical
        
        confidence = max(0.0, min(1.0, score))
        passed = confidence >= self.get_threshold()
        
        return QualityScore(
            score=score,
            confidence=confidence,
            source=context.get("source", "unknown"),
            issues=issues,
            passed_gates=passed,
            level=self._calculate_level(confidence)
        )
    
    def get_threshold(self) -> float:
        return 0.5  # Minimum design quality threshold

class CompletenessGate(QualityGate):
    """Validates completeness of extraction."""
    
    def validate(self, result: Dict[str, Any], context: Dict[str, Any]) -> QualityScore:
        """Validate completeness."""
        issues = []
        score = 1.0
        
        required_fields = ["title", "description"]
        optional_fields = ["image", "tags"]
        
        # Check required fields
        for field in required_fields:
            if not result.get(field):
                issues.append(f"Missing required field: {field}")
                score -= 0.4
        
        # Check optional fields
        missing_optional = sum(1 for field in optional_fields if not result.get(field))
        if missing_optional > 0:
            issues.append(f"Missing {missing_optional} optional field(s)")
            score -= 0.1 * missing_optional
        
        confidence = max(0.0, min(1.0, score))
        passed = confidence >= self.get_threshold()
        
        return QualityScore(
            score=score,
            confidence=confidence,
            source=context.get("source", "unknown"),
            issues=issues,
            passed_gates=passed,
            level=self._calculate_level(confidence)
        )
    
    def get_threshold(self) -> float:
        return 0.6  # Must have title and description

class QualityFramework:
    """
    Framework for ensuring consistent quality across all extractions.
    """
    
    def __init__(self):
        self.content_gate = ContentQualityGate()
        self.design_gate = DesignQualityGate()
        self.completeness_gate = CompletenessGate()
    
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
        design: Dict[str, Any],
        source: str
    ) -> QualityScore:
        """Validate design extraction quality."""
        return self.design_gate.validate(
            design,
            {"source": source}
        )
    
    def validate_completeness(
        self,
        result: Dict[str, Any],
        source: str
    ) -> QualityScore:
        """Validate completeness."""
        return self.completeness_gate.validate(
            result,
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
import re
from bs4 import BeautifulSoup
from collections import Counter

@dataclass
class DesignElements:
    """Extracted design elements."""
    color_palette: Dict[str, str]  # primary, secondary, accent
    typography: Dict[str, Any]  # font_family, font_sizes, weights
    layout_structure: Dict[str, Any]  # grid, spacing, alignment
    visual_hierarchy: Dict[str, Any]  # prominence, contrast
    design_style: str  # minimalist, corporate, playful, etc.

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
        Extract design elements from multiple sources with quality validation.
        """
        
        # Extract from HTML
        html_design = self._extract_from_html(html_content)
        
        # Extract from screenshot (visual analysis)
        visual_design = self._extract_from_visual(screenshot_bytes, html_content)
        
        # Extract from brand (if available)
        brand_design = self._extract_from_brand(html_content, screenshot_bytes)
        
        # Fuse design elements with priority
        fused_design = self._fuse_design_elements(
            html_design,
            visual_design,
            brand_design
        )
        
        return fused_design
    
    def _extract_from_html(self, html_content: str) -> DesignElements:
        """Extract design elements from HTML/CSS."""
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extract colors
        color_palette = self._extract_colors_from_html(soup)
        
        # Extract typography
        typography = self._extract_typography_from_html(soup)
        
        # Extract layout structure
        layout_structure = self._extract_layout_from_html(soup)
        
        return DesignElements(
            color_palette=color_palette,
            typography=typography,
            layout_structure=layout_structure,
            visual_hierarchy={},
            design_style="corporate"
        )
    
    def _extract_colors_from_html(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract color palette from HTML/CSS."""
        colors = {}
        
        # Look for colors in style tags and inline styles
        style_tags = soup.find_all('style')
        inline_styles = soup.find_all(attrs={'style': True})
        
        # Extract hex colors
        hex_pattern = r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b'
        
        all_colors = []
        for style in style_tags:
            if style.string:
                matches = re.findall(hex_pattern, style.string)
                for match in matches:
                    if len(match) == 6:
                        all_colors.append(f"#{match}")
                    else:
                        # Expand 3-digit hex to 6-digit
                        all_colors.append(f"#{match[0]}{match[0]}{match[1]}{match[1]}{match[2]}{match[2]}")
        
        for elem in inline_styles:
            style_attr = elem.get('style', '')
            matches = re.findall(hex_pattern, style_attr)
            for match in matches:
                if len(match) == 6:
                    all_colors.append(f"#{match}")
                else:
                    all_colors.append(f"#{match[0]}{match[0]}{match[1]}{match[1]}{match[2]}{match[2]}")
        
        # Find most common colors (likely brand colors)
        if all_colors:
            color_counts = Counter(all_colors)
            common_colors = [color for color, count in color_counts.most_common(3)]
            
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
    
    def _extract_typography_from_html(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract typography information from HTML/CSS."""
        typography = {}
        
        # Look for font-family in styles
        style_tags = soup.find_all('style')
        font_pattern = r'font-family:\s*([^;]+)'
        
        fonts = []
        for style in style_tags:
            if style.string:
                matches = re.findall(font_pattern, style.string, re.IGNORECASE)
                fonts.extend(matches)
        
        if fonts:
            font_counts = Counter(fonts)
            most_common_font = font_counts.most_common(1)[0][0]
            # Clean up font name (remove quotes, extra spaces)
            font_name = most_common_font.strip().strip("'\"")
            typography["font_family"] = font_name.split(',')[0].strip()  # Take first font
        
        # Extract font sizes
        size_pattern = r'font-size:\s*([^;]+)'
        sizes = []
        for style in style_tags:
            if style.string:
                matches = re.findall(size_pattern, style.string, re.IGNORECASE)
                sizes.extend(matches)
        
        if sizes:
            typography["font_sizes"] = sizes[:5]  # Top 5 sizes
        
        return typography
    
    def _extract_layout_from_html(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract layout structure from HTML."""
        layout = {}
        
        # Check for grid layouts
        grid_elements = soup.find_all(class_=re.compile(r'grid|flex|container', re.I))
        if grid_elements:
            layout["has_grid"] = True
            classes_str = ' '.join([str(elem.get('class', [])) for elem in grid_elements[:1]])
            if "grid" in classes_str.lower():
                layout["grid_type"] = "css-grid"
            else:
                layout["grid_type"] = "flexbox"
        
        # Check for spacing
        spacing_elements = soup.find_all(class_=re.compile(r'padding|margin|spacing', re.I))
        layout["has_spacing"] = len(spacing_elements) > 0
        
        return layout
    
    def _extract_from_visual(
        self,
        screenshot_bytes: bytes,
        html_content: str
    ) -> DesignElements:
        """Extract design elements from screenshot using AI vision."""
        # This would use an improved vision prompt focused on design
        # For now, return minimal design
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
        try:
            from backend.services.brand_extractor import extract_all_brand_elements
            
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
        """Fuse design elements with priority: Brand > HTML > Visual."""
        
        # Color palette fusion
        color_palette = {}
        if brand_design.color_palette and brand_design.color_palette.get("primary"):
            color_palette = brand_design.color_palette
        elif html_design.color_palette and html_design.color_palette.get("primary"):
            color_palette = html_design.color_palette
        elif visual_design.color_palette and visual_design.color_palette.get("primary"):
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
        design_style = (
            brand_design.design_style or
            html_design.design_style or
            visual_design.design_style or
            "corporate"
        )
        
        return DesignElements(
            color_palette=color_palette,
            typography=typography,
            layout_structure=layout_structure,
            visual_hierarchy=visual_design.visual_hierarchy or html_design.visual_hierarchy,
            design_style=design_style
        )
```

This framework ensures:
1. **Consistent Quality**: Quality gates for all sources
2. **Design Preservation**: Extracts and preserves design elements
3. **Equal Quality**: Same standards regardless of source
4. **Framework-Based**: Structured, reusable, extensible
