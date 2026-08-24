"""
Value Proposition Extractor - Compelling Hook & Benefit Extraction.

PHASE 2 IMPLEMENTATION:
Extracts the most compelling value proposition from page content.
Goes beyond raw text extraction to distill:
- The ONE compelling hook that makes users want to click
- Benefits (not features) that resonate emotionally
- Emotional triggers that drive engagement
- Optimized CTAs that match the value proposition

This is the "copy intelligence" layer that transforms raw content
into click-worthy preview text.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# EMOTIONAL TRIGGERS
# =============================================================================

class EmotionalTrigger(Enum):
    """Primary emotional triggers that drive clicks."""
    CURIOSITY = "curiosity"      # "What happens when..." "The secret to..."
    FEAR = "fear"                # "Don't miss..." "Before it's too late..."
    ASPIRATION = "aspiration"    # "Become..." "Achieve..." "Transform..."
    URGENCY = "urgency"          # "Now" "Today" "Limited time"
    SOCIAL_PROOF = "social_proof"  # "10,000+ users" "Trusted by..."
    EXCLUSIVITY = "exclusivity"  # "Only for..." "VIP" "Exclusive"
    SIMPLICITY = "simplicity"    # "Easy" "Simple" "One-click"
    AUTHORITY = "authority"      # "Expert" "Official" "#1"
    VALUE = "value"              # "Free" "Save" "Best deal"
    NOVELTY = "novelty"          # "New" "First" "Revolutionary"


# Trigger detection patterns
TRIGGER_PATTERNS = {
    EmotionalTrigger.CURIOSITY: [
        r"(?:how|what|why|when)\s+(?:to|do|does|is|are|can)",
        r"(?:secret|discover|reveal|uncover|learn)",
        r"(?:you\s+won't\s+believe|surprising|unexpected)",
    ],
    EmotionalTrigger.FEAR: [
        r"(?:don't\s+miss|before\s+it's\s+too\s+late|last\s+chance)",
        r"(?:warning|avoid|mistake|problem|risk)",
        r"(?:stop|never|without)",
    ],
    EmotionalTrigger.ASPIRATION: [
        r"(?:become|achieve|transform|unlock|master)",
        r"(?:dream|goal|success|growth|improve)",
        r"(?:level\s+up|next\s+level|upgrade)",
    ],
    EmotionalTrigger.URGENCY: [
        r"(?:now|today|limited|hurry|fast)",
        r"(?:ending\s+soon|act\s+fast|immediately)",
        r"(?:\d+\s+(?:hours?|days?|left))",
    ],
    EmotionalTrigger.SOCIAL_PROOF: [
        r"(?:\d+[,\d]*\+?\s+(?:users?|customers?|companies|teams?))",
        r"(?:trusted\s+by|used\s+by|loved\s+by|rated)",
        r"(?:reviews?|testimonials?|stories)",
    ],
    EmotionalTrigger.EXCLUSIVITY: [
        r"(?:exclusive|vip|premium|elite|only\s+for)",
        r"(?:invite|members?\s+only|private)",
        r"(?:limited\s+(?:access|edition|spots?))",
    ],
    EmotionalTrigger.SIMPLICITY: [
        r"(?:easy|simple|effortless|seamless|intuitive)",
        r"(?:one-click|no\s+code|automated|instant)",
        r"(?:minutes|seconds|quick)",
    ],
    EmotionalTrigger.AUTHORITY: [
        r"(?:#1|number\s+one|best|leading|top)",
        r"(?:expert|official|certified|award)",
        r"(?:industry|enterprise|professional)",
    ],
    EmotionalTrigger.VALUE: [
        r"(?:free|save|discount|deal|offer)",
        r"(?:affordable|budget|value|cheap)",
        r"(?:\$?\d+\s*(?:off|%|saved))",
    ],
    EmotionalTrigger.NOVELTY: [
        r"(?:new|first|latest|introducing|announcing)",
        r"(?:revolutionary|innovative|cutting-edge|breakthrough)",
        r"(?:2024|2025|next-gen)",
    ],
}


# =============================================================================
# FEATURE TO BENEFIT MAPPINGS
# =============================================================================

# Common feature patterns and their benefit transformations
FEATURE_TO_BENEFIT = {
    # Speed features
    r"(?:fast|quick|rapid|instant)": "Save hours every week",
    r"(?:\d+x\s+faster)": "Get more done in less time",
    r"(?:real-?time)": "See results instantly",
    
    # Automation features
    r"(?:automat\w+|auto-)": "Work smarter, not harder",
    r"(?:ai|machine\s+learning|artificial\s+intelligence)": "AI does the heavy lifting",
    r"(?:smart|intelligent)": "Technology that thinks for you",
    
    # Simplicity features
    r"(?:no\s+code|drag\s+and\s+drop)": "Build without coding",
    r"(?:one-click|single\s+click)": "One click is all it takes",
    r"(?:intuitive|easy\s+to\s+use)": "Get started in minutes",
    
    # Security features
    r"(?:secure|encrypted|protected)": "Your data stays safe",
    r"(?:privacy|private|confidential)": "Your privacy protected",
    r"(?:compliant|gdpr|soc\s*2)": "Enterprise-grade security",
    
    # Scale features
    r"(?:unlimited|infinite|no\s+limits?)": "Grow without limits",
    r"(?:scalable|scales?)": "Grows with your needs",
    r"(?:enterprise|teams?)": "Built for teams of any size",
    
    # Integration features
    r"(?:integrat\w+|connect\w*)": "Works with tools you love",
    r"(?:api|sdk|webhook)": "Connects to everything",
    r"(?:import|export|sync)": "Seamless data flow",
    
    # Analytics features
    r"(?:analytics?|insights?|metrics?)": "See what's working",
    r"(?:dashboard|report\w*)": "All your data at a glance",
    r"(?:track\w*|monitor\w*)": "Know exactly what's happening",
    
    # Collaboration features
    r"(?:collaborat\w+|team\w*)": "Work better together",
    r"(?:share|sharing)": "Share with anyone easily",
    r"(?:comment\w*|feedback)": "Get feedback faster",
    
    # Support features
    r"(?:24/7|support|help)": "Help whenever you need it",
    r"(?:documentation|docs|guides?)": "Learn at your own pace",
    r"(?:community|forum)": "Join a thriving community",
}


# =============================================================================
# CTA TEMPLATES
# =============================================================================

CTA_TEMPLATES = {
    "saas": ["Start Free Trial", "Get Started Free", "Try It Free", "Start Building"],
    "product": ["Shop Now", "Buy Now", "Add to Cart", "Get Yours"],
    "article": ["Read More", "Learn More", "Discover", "Explore"],
    "profile": ["Connect", "Follow", "View Profile", "Learn More"],
    "landing": ["Get Started", "Sign Up Free", "Join Now", "Start Today"],
    "tool": ["Use Free", "Try Now", "Launch Tool", "Get Access"],
    "default": ["Learn More", "Get Started", "Discover", "Explore"],
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ValueProposition:
    """Extracted value proposition with all components."""
    
    # The compelling hook (max 10 words)
    hook: str
    
    # Primary benefit statement
    primary_benefit: str
    
    # Secondary benefits
    secondary_benefits: List[str] = field(default_factory=list)
    
    # Detected emotional trigger
    emotional_trigger: Optional[EmotionalTrigger] = None
    trigger_strength: float = 0.0  # 0.0-1.0
    
    # Optimized CTA
    cta: str = "Learn More"
    
    # Social proof (if found)
    social_proof: Optional[str] = None
    
    # Confidence score
    confidence: float = 0.0
    
    # Original vs optimized
    original_title: str = ""
    original_description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook": self.hook,
            "primary_benefit": self.primary_benefit,
            "secondary_benefits": self.secondary_benefits,
            "emotional_trigger": self.emotional_trigger.value if self.emotional_trigger else None,
            "trigger_strength": self.trigger_strength,
            "cta": self.cta,
            "social_proof": self.social_proof,
            "confidence": self.confidence,
            "original_title": self.original_title,
            "original_description": self.original_description
        }


# =============================================================================
# VALUE PROP EXTRACTOR
# =============================================================================

class ValuePropExtractor:
    """
    Extracts compelling value propositions from page content.
    
    Transforms raw titles and descriptions into click-worthy hooks
    that resonate emotionally with viewers.
    """
    
    def __init__(
        self,
        max_hook_words: int = 12,
        max_benefit_words: int = 20,
        use_ai: bool = True
    ):
        """
        Initialize extractor.
        
        Args:
            max_hook_words: Maximum words in hook
            max_benefit_words: Maximum words in benefit
            use_ai: Whether to use AI for enhancement (requires API key)
        """
        self.max_hook_words = max_hook_words
        self.max_benefit_words = max_benefit_words
        self.use_ai = use_ai
        
        logger.info(
            f"ValuePropExtractor initialized: "
            f"max_hook={max_hook_words}, max_benefit={max_benefit_words}, "
            f"use_ai={use_ai}"
        )
    
    def extract(
        self,
        title: str,
        description: Optional[str] = None,
        features: Optional[List[str]] = None,
        page_type: str = "default",
        social_proof: Optional[str] = None,
        url: Optional[str] = None
    ) -> ValueProposition:
        """
        Extract compelling value proposition from content.
        
        Args:
            title: Page title
            description: Page description
            features: List of features (will be converted to benefits)
            page_type: Type of page (saas, product, article, etc.)
            social_proof: Pre-extracted social proof
            url: Page URL for context
            
        Returns:
            ValueProposition with optimized content
        """
        logger.info(f"📝 Extracting value prop from: {title[:50]}...")
        
        # Clean inputs
        title = self._clean_text(title or "")
        description = self._clean_text(description or "")
        features = features or []
        
        # 1. Detect emotional triggers
        trigger, strength = self._detect_emotional_trigger(title, description)
        
        # 2. Extract or detect social proof
        if not social_proof:
            social_proof = self._extract_social_proof(title, description)
        
        # 3. Convert features to benefits
        benefits = self._convert_features_to_benefits(features)
        
        # 4. Generate compelling hook
        hook = self._generate_hook(title, description, trigger)
        
        # 5. Generate primary benefit
        primary_benefit = self._generate_primary_benefit(
            description, benefits, trigger
        )
        
        # 6. Get optimized CTA
        cta = self._get_optimal_cta(page_type, trigger)
        
        # 7. Calculate confidence
        confidence = self._calculate_confidence(
            hook, primary_benefit, trigger, strength, social_proof
        )
        
        result = ValueProposition(
            hook=hook,
            primary_benefit=primary_benefit,
            secondary_benefits=benefits[:3],
            emotional_trigger=trigger,
            trigger_strength=strength,
            cta=cta,
            social_proof=social_proof,
            confidence=confidence,
            original_title=title,
            original_description=description
        )
        
        logger.info(
            f"✅ Value prop extracted: hook='{hook[:30]}...', "
            f"trigger={trigger.value if trigger else 'none'}, "
            f"confidence={confidence:.2f}"
        )
        
        return result
    
    def extract_with_ai(
        self,
        title: str,
        description: Optional[str] = None,
        features: Optional[List[str]] = None,
        page_type: str = "default"
    ) -> ValueProposition:
        """
        Extract value proposition using AI enhancement.
        
        Falls back to rule-based extraction if AI fails.
        """
        # First, try rule-based extraction
        rule_based = self.extract(title, description, features, page_type)
        
        if not self.use_ai:
            return rule_based
        
        try:
            from backend.services.preview.reasoning.models import spec_for
            from backend.services.reasoning_client import get_client

            # Copy work, not vision: the small model is as good at it and the
            # shared client is the one that actually points at the gateway.
            spec = spec_for("copy_refinement")
            client = get_client(timeout=spec.timeout_s)
            
            prompt = f"""Transform this page content into a compelling value proposition.

TITLE: {title}
DESCRIPTION: {description or 'None'}
FEATURES: {', '.join(features) if features else 'None'}
PAGE TYPE: {page_type}

Create:
1. HOOK: A compelling headline (max 10 words) that makes people want to click.
   - Focus on the ONE main benefit
   - Use power words that trigger emotion
   - Be specific, not generic

2. BENEFIT: The primary benefit statement (max 20 words).
   - Focus on outcomes, not features
   - Answer "What's in it for me?"
   - Be concrete and specific

3. CTA: The perfect call-to-action (2-4 words).

Respond in JSON:
{{"hook": "...", "benefit": "...", "cta": "..."}}"""
            
            response = client.chat.completions.create(
                **spec.request_kwargs_without_tokens(),
                messages=[
                    {"role": "system", "content": "You are a conversion copywriter who writes compelling headlines."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            # Merge AI results with rule-based
            rule_based.hook = result.get("hook", rule_based.hook)
            rule_based.primary_benefit = result.get("benefit", rule_based.primary_benefit)
            rule_based.cta = result.get("cta", rule_based.cta)
            rule_based.confidence = min(rule_based.confidence + 0.2, 1.0)
            
            logger.info(f"🤖 AI-enhanced value prop: {rule_based.hook}")
            
            return rule_based
            
        except Exception as e:
            logger.warning(f"AI enhancement failed, using rule-based: {e}")
            return rule_based
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove common suffixes
        suffixes = [
            r'\s*[-|–]\s*[^-|–]+$',  # " - Site Name"
            r'\s*\|\s*[^|]+$',  # " | Site Name"
            r'\s*::\s*[^:]+$',  # " :: Site Name"
        ]
        for suffix in suffixes:
            text = re.sub(suffix, '', text)
        
        return text.strip()
    
    def _detect_emotional_trigger(
        self,
        title: str,
        description: str
    ) -> Tuple[Optional[EmotionalTrigger], float]:
        """Detect the primary emotional trigger in content."""
        combined = f"{title} {description}".lower()
        
        best_trigger = None
        best_score = 0.0
        
        for trigger, patterns in TRIGGER_PATTERNS.items():
            matches = 0
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    matches += 1
            
            score = matches / len(patterns)
            if score > best_score:
                best_score = score
                best_trigger = trigger
        
        # Only return if above threshold
        if best_score >= 0.2:
            return best_trigger, best_score
        
        return None, 0.0
    
    def _extract_social_proof(self, title: str, description: str) -> Optional[str]:
        """Extract social proof statements."""
        combined = f"{title} {description}"
        
        # Look for number + users/customers pattern
        patterns = [
            r'(\d+[,\d]*\+?\s*(?:users?|customers?|companies|teams?|people))',
            r'(trusted\s+by\s+[\w\s,]+)',
            r'(rated\s+[\d.]+\s*(?:/\s*\d+|stars?))',
            r'(\d+[,\d]*\+?\s*(?:reviews?|ratings?))',
            r'(used\s+by\s+[\w\s,]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _convert_features_to_benefits(self, features: List[str]) -> List[str]:
        """Convert feature statements to benefit statements."""
        benefits = []
        
        for feature in features:
            feature_lower = feature.lower()
            benefit_found = False
            
            for pattern, benefit in FEATURE_TO_BENEFIT.items():
                if re.search(pattern, feature_lower, re.IGNORECASE):
                    benefits.append(benefit)
                    benefit_found = True
                    break
            
            # If no pattern matched, try to generate a benefit
            if not benefit_found:
                benefit = self._generate_benefit_from_feature(feature)
                if benefit:
                    benefits.append(benefit)
        
        return benefits
    
    def _generate_benefit_from_feature(self, feature: str) -> Optional[str]:
        """Generate a benefit statement from a feature."""
        # Simple transformation rules
        transformations = [
            (r'^(?:with\s+)?(\w+)\s+support$', r'Get help with \1'),
            (r'^(\w+)\s+integration$', r'Connect your \1'),
            (r'^(\w+)\s+analytics?$', r'Understand your \1'),
            (r'^(\w+)\s+management$', r'Manage your \1 easily'),
            (r'^(\w+)\s+automation$', r'Automate your \1'),
        ]
        
        for pattern, replacement in transformations:
            if re.match(pattern, feature, re.IGNORECASE):
                return re.sub(pattern, replacement, feature, flags=re.IGNORECASE)
        
        return None
    
    def _generate_hook(
        self,
        title: str,
        description: str,
        trigger: Optional[EmotionalTrigger]
    ) -> str:
        """Generate a compelling hook from content."""
        # Start with the title
        hook = title
        
        # If title is too long, try to shorten
        words = hook.split()
        if len(words) > self.max_hook_words:
            # Try to find a natural break
            for i in range(min(10, len(words)), 0, -1):
                partial = ' '.join(words[:i])
                # Check for sentence boundary
                if partial.endswith(('.', '!', '?', '-', ':')):
                    hook = partial.rstrip('.-:')
                    break
            else:
                hook = ' '.join(words[:self.max_hook_words])
        
        # Add trigger-based enhancements if hook is weak
        if len(hook) < 20 and trigger:
            hook = self._enhance_with_trigger(hook, trigger)
        
        return hook
    
    def _enhance_with_trigger(self, hook: str, trigger: EmotionalTrigger) -> str:
        """Enhance a weak hook with emotional trigger."""
        enhancements = {
            EmotionalTrigger.CURIOSITY: f"Discover {hook}",
            EmotionalTrigger.ASPIRATION: f"Achieve More with {hook}",
            EmotionalTrigger.SIMPLICITY: f"{hook} Made Simple",
            EmotionalTrigger.NOVELTY: f"The New Way to {hook}",
            EmotionalTrigger.VALUE: f"Get {hook} Free",
        }
        
        return enhancements.get(trigger, hook)
    
    def _generate_primary_benefit(
        self,
        description: str,
        benefits: List[str],
        trigger: Optional[EmotionalTrigger]
    ) -> str:
        """Generate the primary benefit statement."""
        # If we have converted benefits, use the first one
        if benefits:
            return benefits[0]
        
        # Otherwise, try to extract from description
        if description:
            # Get first sentence
            sentences = re.split(r'[.!?]', description)
            if sentences and len(sentences[0].strip()) > 10:
                benefit = sentences[0].strip()
                words = benefit.split()
                if len(words) > self.max_benefit_words:
                    benefit = ' '.join(words[:self.max_benefit_words])
                return benefit
        
        # Fallback based on trigger
        fallbacks = {
            EmotionalTrigger.SIMPLICITY: "Get started in minutes",
            EmotionalTrigger.VALUE: "Save time and money",
            EmotionalTrigger.ASPIRATION: "Reach your goals faster",
            EmotionalTrigger.SOCIAL_PROOF: "Join thousands of happy users",
            EmotionalTrigger.NOVELTY: "Experience the future today",
        }
        
        if trigger and trigger in fallbacks:
            return fallbacks[trigger]
        
        return "Discover a better way"
    
    def _get_optimal_cta(
        self,
        page_type: str,
        trigger: Optional[EmotionalTrigger]
    ) -> str:
        """Get the optimal CTA for the context."""
        # Get base CTAs for page type
        ctas = CTA_TEMPLATES.get(page_type.lower(), CTA_TEMPLATES["default"])
        
        # Modify based on trigger
        if trigger == EmotionalTrigger.URGENCY:
            return "Start Now"
        elif trigger == EmotionalTrigger.VALUE:
            return "Get It Free"
        elif trigger == EmotionalTrigger.EXCLUSIVITY:
            return "Get Access"
        elif trigger == EmotionalTrigger.CURIOSITY:
            return "See How"
        
        return ctas[0]
    
    def _calculate_confidence(
        self,
        hook: str,
        benefit: str,
        trigger: Optional[EmotionalTrigger],
        trigger_strength: float,
        social_proof: Optional[str]
    ) -> float:
        """Calculate confidence in the value proposition."""
        score = 0.0
        
        # Hook quality (0-0.3)
        if len(hook) >= 20:
            score += 0.15
        if len(hook) >= 40:
            score += 0.15
        
        # Benefit quality (0-0.3)
        if len(benefit) >= 20:
            score += 0.15
        if len(benefit) >= 40:
            score += 0.15
        
        # Emotional trigger (0-0.2)
        if trigger:
            score += 0.1 + (trigger_strength * 0.1)
        
        # Social proof (0-0.2)
        if social_proof:
            score += 0.2
        
        return min(1.0, score)


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_extractor_instance: Optional[ValuePropExtractor] = None


def get_value_prop_extractor() -> ValuePropExtractor:
    """Get singleton ValuePropExtractor instance."""
    global _extractor_instance
    
    if _extractor_instance is None:
        _extractor_instance = ValuePropExtractor()
    
    return _extractor_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def extract_value_proposition(
    title: str,
    description: Optional[str] = None,
    features: Optional[List[str]] = None,
    page_type: str = "default"
) -> ValueProposition:
    """
    Convenience function to extract value proposition.
    
    Args:
        title: Page title
        description: Page description
        features: List of features
        page_type: Type of page
        
    Returns:
        ValueProposition with optimized content
    """
    return get_value_prop_extractor().extract(
        title, description, features, page_type
    )


def generate_hook(
    title: str,
    description: Optional[str] = None
) -> str:
    """
    Generate a compelling hook from title and description.
    
    Args:
        title: Page title
        description: Page description
        
    Returns:
        Compelling hook string
    """
    vp = get_value_prop_extractor().extract(title, description)
    return vp.hook


def detect_emotional_trigger(
    text: str
) -> Tuple[Optional[str], float]:
    """
    Detect the primary emotional trigger in text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Tuple of (trigger_name, strength)
    """
    extractor = get_value_prop_extractor()
    trigger, strength = extractor._detect_emotional_trigger(text, "")
    return (trigger.value if trigger else None, strength)

