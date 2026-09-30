"""SQLAlchemy ORM models module."""
# Base is imported from db module to avoid circular imports
from backend.db import Base

# Import all models to ensure they're registered with Base
from backend.models.user import User  # noqa: F401
from backend.models.domain import Domain  # noqa: F401
from backend.models.brand import BrandSettings  # noqa: F401
from backend.models.preview import Preview  # noqa: F401
from backend.models.error import Error  # noqa: F401
from backend.models.activity_log import ActivityLog  # noqa: F401
from backend.models.analytics_event import AnalyticsEvent  # noqa: F401
from backend.models.analytics_aggregate import AnalyticsDailyAggregate  # noqa: F401
from backend.models.organization import Organization  # noqa: F401
from backend.models.organization_member import OrganizationMember, OrganizationRole  # noqa: F401
from backend.models.preview_variant import PreviewVariant  # noqa: F401
from backend.models.preview_job_failure import PreviewJobFailure  # noqa: F401
from backend.models.blog_post import BlogPost, BlogCategory  # noqa: F401
from backend.models.newsletter_subscriber import NewsletterSubscriber  # noqa: F401
from backend.models.organization_invite import OrganizationInvite  # noqa: F401
from backend.models.api_key import ApiKey  # noqa: F401
from backend.models.published_site import (  # noqa: F401
    PublishedSite, SitePost, SiteCategory, SitePage, SiteMenu, SiteMenuItem,
    SiteMedia, SiteBranding, SiteSettings
)

__all__ = [
    "Base", "User", "Domain", "BrandSettings", "Preview", "Error", "ActivityLog",
    "AnalyticsEvent", "AnalyticsDailyAggregate", "Organization", "OrganizationMember",
    "OrganizationRole", "PreviewVariant", "PreviewJobFailure", "BlogPost", "BlogCategory",
    "NewsletterSubscriber", "PublishedSite", "SitePost", "SiteCategory", "SitePage",
    "SiteMenu", "SiteMenuItem", "SiteMedia", "SiteBranding", "SiteSettings"
]

