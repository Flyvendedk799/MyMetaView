"""Resolving which brand settings apply to a site.

An organization can connect several domains, and each one is its own site with
its own name, colours and card preferences. Brand settings are therefore scoped
per domain.

Two kinds of row live in ``brand_settings``:

* ``domain_id`` set — the settings for that specific domain.
* ``domain_id`` NULL — the organization-wide default. This is the row every
  account had before brands became per-domain, and it is what a domain falls
  back to until it is customised.

Everything that needs a brand goes through here, so the fallback rule is
defined once.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.brand import BrandSettings as BrandSettingsModel
from backend.models.domain import Domain as DomainModel

logger = logging.getLogger(__name__)

DEFAULT_BRAND = {
    "primary_color": "#2979FF",
    "secondary_color": "#0A1A3C",
    "accent_color": "#3FFFD3",
    "font_family": "Inter",
}

# Copied onto a new per-domain row so it starts out looking like the account
# default rather than a blank slate. domain_id and the ownership columns are
# deliberately not in here.
INHERITED_FIELDS = (
    "primary_color",
    "secondary_color",
    "accent_color",
    "font_family",
    "logo_url",
    "brand_name",
    "tagline",
    "brand_description",
    "audience",
    "voice",
    "preview_layout",
    "preview_panel",
    "preview_accent",
    "force_brand_colors",
    "hide_watermark",
)


def get_org_default(db: Session, organization_id: int) -> Optional[BrandSettingsModel]:
    """The organization-wide row, used when a domain has no settings of its own."""
    return (
        db.query(BrandSettingsModel)
        .filter(
            BrandSettingsModel.organization_id == organization_id,
            BrandSettingsModel.domain_id.is_(None),
        )
        .first()
    )


def get_for_domain(
    db: Session, organization_id: int, domain_id: int
) -> Optional[BrandSettingsModel]:
    """The row belonging to this domain, if it has been customised."""
    return (
        db.query(BrandSettingsModel)
        .filter(
            BrandSettingsModel.organization_id == organization_id,
            BrandSettingsModel.domain_id == domain_id,
        )
        .first()
    )


def resolve(
    db: Session, organization_id: int, domain_id: Optional[int] = None
) -> Optional[BrandSettingsModel]:
    """Which brand applies, without creating anything.

    Falls back from the domain's own settings to the organization default, and
    returns None when the account has neither.
    """
    if domain_id is not None:
        settings = get_for_domain(db, organization_id, domain_id)
        if settings is not None:
            return settings
    return get_org_default(db, organization_id)


def resolve_for_domain_name(
    db: Session, organization_id: int, domain_name: Optional[str]
) -> Optional[BrandSettingsModel]:
    """Same as resolve(), for callers that only know the hostname."""
    domain_id = None
    if domain_name:
        domain = (
            db.query(DomainModel)
            .filter(
                DomainModel.organization_id == organization_id,
                DomainModel.name == domain_name,
            )
            .first()
        )
        domain_id = domain.id if domain else None
    return resolve(db, organization_id, domain_id)


def get_or_create(
    db: Session,
    organization_id: int,
    user_id: Optional[int] = None,
    domain_id: Optional[int] = None,
) -> BrandSettingsModel:
    """Return the row for this scope, creating it if it does not exist yet.

    A brand new per-domain row is seeded from the organization default so the
    domain starts where the account left off instead of reverting to stock
    colours. Called from the write paths, where a row has to exist.
    """
    existing = (
        get_for_domain(db, organization_id, domain_id)
        if domain_id is not None
        else get_org_default(db, organization_id)
    )
    if existing is not None:
        return existing

    seed = dict(DEFAULT_BRAND)
    if domain_id is not None:
        parent = get_org_default(db, organization_id)
        if parent is not None:
            for field in INHERITED_FIELDS:
                value = getattr(parent, field, None)
                if value is not None:
                    seed[field] = value

    settings = BrandSettingsModel(
        **seed,
        user_id=user_id,
        organization_id=organization_id,
        domain_id=domain_id,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
