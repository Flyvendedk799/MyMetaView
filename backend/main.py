"""FastAPI application entry point."""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.core.config import settings
from backend.middleware.error_handler import error_handler_middleware
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.middleware.request_id import RequestIDMiddleware
from backend.middleware.request_logging import RequestLoggingMiddleware
from backend.middleware.public_cors import PublicCorsMiddleware
from backend.utils.logger import setup_logging
from backend.api.v1 import routes_auth, routes_domains, routes_brand, routes_previews, routes_analytics, routes_public_preview, routes_jobs, routes_verification, routes_billing, routes_webhooks, routes_activity, routes_tracking, routes_analytics_extended, routes_organizations, routes_preview_variants, routes_account, routes_blog, routes_preview_debug, routes_newsletter, routes_demo, routes_demo_optimized, routes_export, routes_health, routes_sitemap, routes_preview_enhancements, routes_sites, routes_site_cms, routes_public_site, routes_preview_diagnosis, routes_plans
from backend.api.v1 import routes_install
from backend.api import routes_snippet
from backend.api.admin import routes_admin

# DEV ONLY: Testing endpoints (disabled in production)
if os.getenv("ENV", "development").lower() != "production":
    from backend.api.v1 import routes_testing
from backend.db import Base
from backend.db.session import engine
from backend.db.schema_sync import sync_missing_columns

# Setup structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(level=log_level)

# Import all models to ensure they're registered with Base
from backend.models import user, domain, brand, preview, error, activity_log, analytics_event, analytics_aggregate, organization, organization_member, preview_variant, blog_post, newsletter_subscriber, published_site  # noqa: F401


# Create database tables on startup
# NOTE: For schema changes going forward, use Alembic migrations (see backend/README_backend.md).
# This create_all() is kept for initial dev setup, but Alembic is the source of truth for evolving schema.
def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Preview SaaS Dashboard",
    debug=settings.DEBUG if hasattr(settings, 'DEBUG') else False,
)

# Create tables on startup
@app.on_event("startup")
def on_startup():
    """Initialize database tables on application startup."""
    import logging
    from alembic.config import Config
    from alembic import command
    
    logger = logging.getLogger(__name__)
    
    # Run database migrations automatically on startup (production)
    # Migrations are idempotent and safe to run multiple times
    if os.getenv("ENV", "development").lower() == "production":
        try:
            logger.info("Running database migrations...")
            alembic_cfg = Config("alembic.ini")
            # Change to project root to ensure alembic.ini is found
            import os as os_module
            original_cwd = os_module.getcwd()
            try:
                project_root = os_module.path.dirname(os_module.path.dirname(os_module.path.abspath(__file__)))
                os_module.chdir(project_root)
                command.upgrade(alembic_cfg, "head")
                logger.info("Database migrations completed successfully")
            finally:
                os_module.chdir(original_cwd)
        except Exception as e:
            logger.error(f"Failed to run database migrations: {e}", exc_info=True)
            # In production, migrations are critical - log error but don't crash
            # Admin should check logs and run migrations manually if needed
            logger.warning("Application starting without migrations. Please run migrations manually.")
    
    logger.info("=" * 60)
    logger.info("Starting Preview SaaS API")
    logger.info(f"Environment: {os.getenv('ENV', 'development')}")
    logger.info(f"API Version: {settings.APP_VERSION}")
    logger.info(f"Debug Mode: {settings.DEBUG if hasattr(settings, 'DEBUG') else False}")
    logger.info(f"CORS Origins: {settings.CORS_ALLOWED_ORIGINS if settings.CORS_ALLOWED_ORIGINS else 'All origins (dev mode)'}")
    logger.info("=" * 60)
    
    try:
        create_tables()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}", exc_info=True)
        raise

    # Local media fallback storage (used when R2 is unconfigured or down).
    # Lives under backend/static so the existing /static mount serves it.
    try:
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create MEDIA_ROOT {settings.MEDIA_ROOT}: {e}")

    # create_all() above only creates missing *tables*. Columns added to an
    # existing table arrive via Alembic — which nothing in the deploy path runs,
    # so they were never applied. Reconcile them here instead of serving 500s.
    try:
        added = sync_missing_columns(engine)
        if added:
            logger.warning(
                "Schema sync added %d missing column(s): %s. "
                "These should have come from an Alembic migration — check that "
                "migrations run on deploy.",
                len(added),
                ", ".join(added),
            )
        else:
            logger.info("Database schema matches the models")
    except Exception as e:
        # Never block startup on this: the app may still serve fine, and the
        # error is more useful in the logs than as a crash loop.
        logger.error(f"Schema sync failed: {e}", exc_info=True)


# Configure CORS
# For development: allow all origins for public preview endpoint
# In production, restrict to specific domains
cors_origins = settings.CORS_ALLOWED_ORIGINS.split(",") if settings.CORS_ALLOWED_ORIGINS else []
if cors_origins:
    # Production: restrict to specific origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
else:
    # Development: allow all origins (for public preview endpoint)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",  # Allow all origins for public preview endpoint (dev only)
        allow_credentials=False,  # Set to False when allowing all origins
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Allow any origin to read the public API. Added after CORSMiddleware so it sits
# further out and wins for the customer origins that policy cannot enumerate.
app.add_middleware(PublicCorsMiddleware)

# Add request ID middleware (first, so all requests have IDs)
app.add_middleware(RequestIDMiddleware)

# Add request logging middleware (after request ID, before security headers)
app.add_middleware(RequestLoggingMiddleware)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add error handling middleware (should be last)
@app.middleware("http")
async def error_middleware(request: Request, call_next):
    return await error_handler_middleware(request, call_next)

# Serve the embed snippet explicitly, before the static mount claims /static/*,
# so it gets the caching and CORS headers a cross-origin asset needs.
app.include_router(routes_snippet.router)

# Mount static files for everything else
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Include public site router FIRST (before API routes)
# This ensures domain-based routing works correctly
app.include_router(
    routes_public_site.router,
)

# Include routers
app.include_router(
    routes_auth.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_domains.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_install.router,
    prefix=settings.API_V1_PREFIX,
)
# Snippet heartbeat: called from customer sites, so it carries its own full path.
app.include_router(
    routes_install.public_router,
)
app.include_router(
    routes_brand.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_previews.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_analytics.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_public_preview.router,
)
app.include_router(
    routes_sitemap.router,
)
app.include_router(
    routes_jobs.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_verification.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_billing.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_webhooks.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_admin.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_activity.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_tracking.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_analytics_extended.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_organizations.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_preview_variants.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_account.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_blog.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_preview_debug.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_preview_diagnosis.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_newsletter.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_demo.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_demo_optimized.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_export.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_health.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_plans.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_preview_enhancements.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_sites.router,
    prefix=settings.API_V1_PREFIX,
)
app.include_router(
    routes_site_cms.router,
    prefix=settings.API_V1_PREFIX,
)
# Note: routes_public_site is included at the top, before API routes

# DEV ONLY: Testing endpoints
if os.getenv("ENV", "development").lower() != "production":
    app.include_router(
        routes_testing.router,
        prefix=settings.API_V1_PREFIX,
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Health check endpoint called")
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
def root(request: Request):
    """
    Root endpoint - returns API info for Railway domain.
    Custom domain requests are handled by routes_public_site router.
    """
    # Check if this is a Railway domain (not a custom domain)
    host = request.headers.get("host", "")
    railway_domains = [".railway.app", ".up.railway.app", "localhost", "127.0.0.1", "0.0.0.0"]
    is_railway_domain = any(railway_domain in host for railway_domain in railway_domains) if host else True
    
    # Only return API info for Railway domains
    # Custom domains are handled by routes_public_site router (mounted first)
    if is_railway_domain:
        return {
            "message": "Preview SaaS API",
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }
    else:
        # This should be handled by public site router, but if it reaches here, return 404
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Site not found")

