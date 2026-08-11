"""Service for managing published sites with plan limit checks."""
import re
from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from backend.models.published_site import (
    PublishedSite, SitePost, SiteCategory, SitePage,
    SiteBranding, SiteSettings
)
from backend.models.domain import Domain
from backend.models.organization import Organization


def get_site_limit_for_plan(subscription_plan: Optional[str]) -> int:
    """
    Get the maximum number of sites allowed for a subscription plan.
    
    Args:
        subscription_plan: Subscription plan name (e.g., 'free', 'pro', 'enterprise')
        
    Returns:
        Maximum number of sites allowed
    """
    # Aligned with core.plans (the canonical table) via resolve_plan_key so
    # legacy Stripe names ("basic", "pro") map to real tiers instead of a
    # separate, drifted plan list.
    from backend.core.plans import resolve_plan_key

    plan_limits = {
        'free': 0,
        'starter': 1,
        'growth': 3,
        'agency': -1,  # unlimited
    }

    key = resolve_plan_key(subscription_plan)
    return plan_limits.get(key, 0)


def check_site_limit(org: Organization, db: Session) -> Tuple[bool, str]:
    """
    Check if organization can create more sites based on their plan.
    
    Args:
        org: Organization instance
        db: Database session
        
    Returns:
        Tuple of (can_create, error_message)
    """
    # Check subscription status
    if org.subscription_status not in ['active', 'trialing']:
        # Check trial period
        if org.trial_ends_at and datetime.utcnow() < org.trial_ends_at:
            # In trial, allow 1 site
            current_count = db.query(func.count(PublishedSite.id)).filter(
                PublishedSite.organization_id == org.id
            ).scalar()
            if current_count >= 1:
                return False, "Trial limit reached. Please upgrade to create more sites."
            return True, ""
        else:
            return False, "Active subscription required to create sites."
    
    # Get plan limit
    limit = get_site_limit_for_plan(org.subscription_plan)
    
    # Unlimited plan
    if limit == -1:
        return True, ""
    
    # Count current sites
    current_count = db.query(func.count(PublishedSite.id)).filter(
        PublishedSite.organization_id == org.id
    ).scalar()
    
    if current_count >= limit:
        return False, f"Plan limit reached. Your {org.subscription_plan or 'current'} plan allows {limit} site(s). Please upgrade to create more sites."
    
    return True, ""


def generate_slug(name: str) -> str:
    """
    Generate URL-friendly slug from name.
    
    Args:
        name: Site name
        
    Returns:
        URL-friendly slug
    """
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    return slug[:200]


def ensure_unique_slug(db: Session, slug: str, exclude_id: Optional[int] = None) -> str:
    """
    Ensure slug is unique, append number if necessary.
    
    Args:
        db: Database session
        slug: Base slug
        exclude_id: Site ID to exclude from uniqueness check
        
    Returns:
        Unique slug
    """
    original_slug = slug
    counter = 1
    while True:
        query = db.query(PublishedSite).filter(PublishedSite.slug == slug)
        if exclude_id:
            query = query.filter(PublishedSite.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{original_slug}-{counter}"
        counter += 1


def get_site_by_id(db: Session, site_id: int, org_id: int) -> Optional[PublishedSite]:
    """
    Get site by ID, ensuring it belongs to the organization.
    
    Args:
        db: Database session
        site_id: Site ID
        org_id: Organization ID
        
    Returns:
        Site instance or None
    """
    from sqlalchemy.orm import joinedload
    return db.query(PublishedSite).options(
        joinedload(PublishedSite.domain)
    ).filter(
        PublishedSite.id == site_id,
        PublishedSite.organization_id == org_id
    ).first()


def get_site_by_domain(db: Session, domain_name: str) -> Optional[PublishedSite]:
    """
    Get site by domain name (for public serving).
    
    Args:
        db: Database session
        domain_name: Domain name
        
    Returns:
        Site instance or None
    """
    from sqlalchemy.orm import joinedload
    
    # Normalize domain name (remove www. prefix for matching, handle case)
    normalized_domain = domain_name.lower().strip()
    if normalized_domain.startswith('www.'):
        normalized_domain = normalized_domain[4:]
    
    # Try exact match first
    site = db.query(PublishedSite).join(
        Domain, PublishedSite.domain_id == Domain.id
    ).filter(
        Domain.name == domain_name,
        PublishedSite.status == 'published',
        PublishedSite.is_active == True
    ).options(
        joinedload(PublishedSite.domain)
    ).first()
    
    # If not found, try without www prefix
    if not site and domain_name.startswith('www.'):
        domain_without_www = domain_name[4:]
        site = db.query(PublishedSite).join(
            Domain, PublishedSite.domain_id == Domain.id
        ).filter(
            Domain.name == domain_without_www,
            PublishedSite.status == 'published',
            PublishedSite.is_active == True
        ).options(
            joinedload(PublishedSite.domain)
        ).first()
    
    # If still not found, try with www prefix
    if not site and not domain_name.startswith('www.'):
        domain_with_www = f'www.{domain_name}'
        site = db.query(PublishedSite).join(
            Domain, PublishedSite.domain_id == Domain.id
        ).filter(
            Domain.name == domain_with_www,
            PublishedSite.status == 'published',
            PublishedSite.is_active == True
        ).options(
            joinedload(PublishedSite.domain)
        ).first()
    
    return site


def create_default_branding(db: Session, site_id: int) -> SiteBranding:
    """
    Create default branding for a new site.
    
    Args:
        db: Database session
        site_id: Site ID
        
    Returns:
        Created SiteBranding instance
    """
    branding = SiteBranding(
        site_id=site_id,
        primary_color="#f97316",
        background_color="#ffffff",
        text_color="#1f2937"
    )
    db.add(branding)
    db.commit()
    db.refresh(branding)
    return branding


def create_default_settings(db: Session, site_id: int) -> SiteSettings:
    """
    Create default settings for a new site.
    
    Args:
        db: Database session
        site_id: Site ID
        
    Returns:
        Created SiteSettings instance
    """
    settings = SiteSettings(
        site_id=site_id,
        language="en",
        timezone="UTC",
        sitemap_enabled=True,
        search_enabled=True
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def publish_site(db: Session, site: PublishedSite) -> PublishedSite:
    """
    Publish a site (set status to published and set published_at).
    
    Args:
        db: Database session
        site: Site instance
        
    Returns:
        Updated site instance
    """
    # Verify domain is verified
    if site.domain.status != 'verified':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain must be verified before publishing site"
        )
    
    site.status = 'published'
    if not site.published_at:
        site.published_at = datetime.utcnow()
    site.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(site)
    return site


def unpublish_site(db: Session, site: PublishedSite) -> PublishedSite:
    """
    Unpublish a site (set status to draft).
    
    Args:
        db: Database session
        site: Site instance
        
    Returns:
        Updated site instance
    """
    site.status = 'draft'
    site.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(site)
    return site


def get_site_stats(db: Session, site_id: int) -> dict:
    """
    Get statistics for a site.
    
    Args:
        db: Database session
        site_id: Site ID
        
    Returns:
        Dictionary with site statistics
    """
    posts_count = db.query(func.count(SitePost.id)).filter(
        SitePost.site_id == site_id
    ).scalar()
    
    published_posts_count = db.query(func.count(SitePost.id)).filter(
        SitePost.site_id == site_id,
        SitePost.status == 'published'
    ).scalar()
    
    categories_count = db.query(func.count(SiteCategory.id)).filter(
        SiteCategory.site_id == site_id,
        SiteCategory.is_active == True
    ).scalar()
    
    pages_count = db.query(func.count(SitePage.id)).filter(
        SitePage.site_id == site_id
    ).scalar()
    
    total_views = db.query(func.sum(SitePost.views_count)).filter(
        SitePost.site_id == site_id
    ).scalar() or 0
    
    return {
        'total_posts': posts_count,
        'published_posts': published_posts_count,
        'draft_posts': posts_count - published_posts_count,
        'categories': categories_count,
        'pages': pages_count,
        'total_views': total_views
    }

