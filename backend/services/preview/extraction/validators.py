"""Deterministic post-extraction validators (Phase 4.2).

Plan requirement: "Reject low-information hooks (e.g., nav-like or generic
phrases). Fallback hierarchy for title/hook:
  1. extracted high-confidence hook
  2. og:title
  3. first semantic H1
  4. domain-derived fallback"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional
from urllib.parse import urlparse

# These phrases indicate the model fell back to navigation / placeholder text
# instead of giving us the brand's actual hook.
_NAV_TOKENS = {
    "home", "about", "about us", "contact", "contact us", "menu",
    "welcome", "welcome to", "untitled", "untitled page", "404",
    "404 not found", "not found", "page not found",
    "loading", "please wait", "sign in", "log in", "register",
    "sign up", "log out", "logout", "search", "blog", "shop",
    "products", "services", "products & services",
}

# Title patterns that almost always mean "the model gave up"
_GENERIC_PHRASES = (
    re.compile(r"^welcome to .{0,40}$", re.IGNORECASE),
    re.compile(r"^our (mission|vision|story).{0,40}$", re.IGNORECASE),
    re.compile(r"^homepage.{0,40}$", re.IGNORECASE),
)


@dataclass
class HookValidationResult:
    is_acceptable: bool
    reasons: List[str] = field(default_factory=list)
    cleaned: Optional[str] = None


def is_low_information_hook(title: str) -> bool:
    """True if the candidate is a nav-like / placeholder / generic phrase."""
    if not title:
        return True
    cleaned = title.strip().lower()
    if not cleaned or len(cleaned) < 4:
        return True
    if cleaned in _NAV_TOKENS:
        return True
    if any(pattern.match(cleaned) for pattern in _GENERIC_PHRASES):
        return True
    if cleaned == cleaned.split()[0] and len(cleaned) < 6:
        return True
    return False


def validate_hook(title: str, *, min_length: int = 5,
                  max_length: int = 110) -> HookValidationResult:
    """Run all rejection rules and produce a cleaned candidate."""
    reasons: List[str] = []
    if not title:
        return HookValidationResult(False, ["empty"], None)

    cleaned = re.sub(r"\s+", " ", title.strip())
    cleaned = cleaned.strip(" -|–—•·")

    if len(cleaned) < min_length:
        reasons.append("too_short")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(" ", 1)[0] + "…"
    if is_low_information_hook(cleaned):
        reasons.append("low_information")

    if reasons:
        return HookValidationResult(False, reasons, None)
    return HookValidationResult(True, [], cleaned)


def fallback_title_chain(
    *,
    extracted_hook: Optional[str],
    og_title: Optional[str],
    h1_candidates: Optional[Iterable[str]],
    url: str,
) -> str:
    """Apply the plan's deterministic fallback hierarchy."""
    candidates: List[str] = []

    if extracted_hook:
        result = validate_hook(extracted_hook)
        if result.is_acceptable and result.cleaned:
            return result.cleaned

    if og_title:
        result = validate_hook(og_title)
        if result.is_acceptable and result.cleaned:
            return result.cleaned

    if h1_candidates:
        for candidate in h1_candidates:
            result = validate_hook(candidate or "")
            if result.is_acceptable and result.cleaned:
                return result.cleaned
            candidates.append(candidate or "")

    parsed = urlparse(url) if url else None
    if parsed and parsed.netloc:
        # Strip a leading "www." label only; lstrip() strips a character SET,
        # which mangles hosts like "w3.org" -> "3.org".
        host = parsed.netloc
        if host.startswith("www."):
            host = host[4:]
        host_clean = host.split(":")[0]
        # Drop TLD for visual brand-y output ("notion.so" → "Notion")
        first_label = host_clean.split(".")[0]
        return first_label.replace("-", " ").title()

    return "Untitled"
