"""Canonical subscription plans — the single source of truth for tiers, limits,
and gated features. Both billing and enforcement read from here.

A plan's numeric limits: an int is the cap; None means unlimited.

Two preview limits, and the difference matters:

``previews_month``     how many previews the account may hold per month, at all.
``ai_previews_month``  how many of those get the full AI treatment — the art
                       director reads the actual page and designs a card for it.

Past the AI allowance the account keeps generating, but on the template lane:
the page's own metadata rendered through the same premium card. Cheaper for us,
still presentable for them, and the obvious reason to upgrade.
"""
import os
from datetime import datetime
from typing import Optional

# --- Gated feature keys -----------------------------------------------------
F_BRAND = "brand_customization"     # colours / logo / font
F_CARD_CONTROLS = "card_controls"   # layout / panel / accent overrides
F_HIDE_WATERMARK = "hide_watermark" # white-label the share cards
F_VARIANTS = "variants"             # A/B/C variants
F_ADV_ANALYTICS = "advanced_analytics"
F_API = "api_access"
F_TEAM = "team_seats"
F_WHITE_LABEL = "white_label"

# --- Tiers ------------------------------------------------------------------
PLANS = {
    "free": {
        "key": "free", "name": "Free", "price": 0,
        "domains": 1, "previews_month": 25, "ai_previews_month": 5, "team_seats": 1,
        "features": set(),
    },
    "starter": {
        "key": "starter", "name": "Starter", "price": 19,
        "domains": 3, "previews_month": 500, "ai_previews_month": 100, "team_seats": 1,
        "features": {F_BRAND},
        "stripe_env": "STRIPE_PRICE_TIER_BASIC",
    },
    "growth": {
        "key": "growth", "name": "Growth", "price": 49,
        "domains": 15, "previews_month": 5000, "ai_previews_month": 1000, "team_seats": 3,
        "features": {F_BRAND, F_CARD_CONTROLS, F_HIDE_WATERMARK, F_VARIANTS, F_ADV_ANALYTICS},
        "stripe_env": "STRIPE_PRICE_TIER_PRO",
    },
    "agency": {
        "key": "agency", "name": "Agency", "price": 149,
        "domains": None, "previews_month": None, "ai_previews_month": None, "team_seats": None,
        "features": {F_BRAND, F_CARD_CONTROLS, F_HIDE_WATERMARK, F_VARIANTS,
                     F_ADV_ANALYTICS, F_API, F_TEAM, F_WHITE_LABEL},
        "stripe_env": "STRIPE_PRICE_TIER_AGENCY",
    },
}

# Legacy / Stripe plan names → canonical key
ALIASES = {
    "basic": "starter", "pro": "growth", "agency": "agency",
    "starter": "starter", "growth": "growth", "free": "free",
}

TRIAL_PLAN = "growth"  # a 14-day trial grants Growth-level access
TRIAL_DAYS = 14


def resolve_plan_key(org) -> str:
    """Resolve an organization's effective plan key from its subscription state."""
    sub_status = (getattr(org, "subscription_status", None) or "").lower()
    plan_name = (getattr(org, "subscription_plan", None) or "").lower()
    key = ALIASES.get(plan_name)

    if sub_status == "active" and key:
        return key
    if sub_status == "trialing":
        trial_ends = getattr(org, "trial_ends_at", None)
        if trial_ends is None or trial_ends > datetime.utcnow():
            return key or TRIAL_PLAN
    return "free"


def get_plan(org) -> dict:
    return PLANS[resolve_plan_key(org)]


def plan_limit(org, limit_key: str) -> Optional[int]:
    """Return the numeric limit (None == unlimited)."""
    return get_plan(org).get(limit_key)


def has_feature(org, feature: str) -> bool:
    return feature in get_plan(org)["features"]


def price_id_to_plan_key(price_id: str) -> Optional[str]:
    """Map a Stripe price ID back to a plan key via env config."""
    if not price_id:
        return None
    for key, p in PLANS.items():
        env = p.get("stripe_env")
        if env and os.getenv(env) == price_id:
            return key
    return None


def public_plans() -> list:
    """Serializable tier list for the pricing/billing UI (no python sets).

    Includes each tier's Stripe price id so the frontend never needs its own
    copy of the price configuration (a missing VITE_ var used to silently turn
    a plan into "Coming soon").
    """
    from backend.core.config import settings

    price_ids = {
        "starter": settings.STRIPE_PRICE_TIER_BASIC,
        "growth": settings.STRIPE_PRICE_TIER_PRO,
        "agency": settings.STRIPE_PRICE_TIER_AGENCY,
    }
    order = ["starter", "growth", "agency"]
    out = []
    for k in order:
        p = PLANS[k]
        out.append({
            "key": p["key"], "name": p["name"], "price": p["price"],
            "domains": p["domains"], "previews_month": p["previews_month"],
            "ai_previews_month": p["ai_previews_month"],
            "team_seats": p["team_seats"], "features": sorted(p["features"]),
            "price_id": price_ids.get(k) or None,
        })
    return out
