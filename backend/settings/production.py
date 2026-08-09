"""Production settings for Railway deployment."""
import os
from typing import List


class ProductionSettings:
    """Production-specific settings with strict environment variable requirements."""
    
    # Debug mode - MUST be False in production
    DEBUG: bool = False
    
    # Allowed hosts for production (Railway provides domain)
    ALLOWED_HOSTS: List[str] = [
        os.getenv("RAILWAY_PUBLIC_DOMAIN", ""),
        os.getenv("API_DOMAIN", ""),
    ]
    # Filter out empty strings
    ALLOWED_HOSTS = [host for host in ALLOWED_HOSTS if host]
    
    # Database URL - REQUIRED in production (PostgreSQL on Railway)
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is required in production")
    
    # Security settings - REQUIRED in production
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required in production")
    
    ALGORITHM: str = "HS256"
    # Production: 7 days token expiry (more user-friendly)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60  # 7 days
    
    # CORS - REQUIRED in production
    CORS_ALLOWED_ORIGINS: str = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if not CORS_ALLOWED_ORIGINS:
        raise ValueError("CORS_ALLOWED_ORIGINS environment variable is required in production")
    
    # Parse CORS origins
    ALLOWED_ORIGINS: List[str] = [
        origin.strip() 
        for origin in CORS_ALLOWED_ORIGINS.split(",") 
        if origin.strip()
    ]
    
    # API version
    API_V1_PREFIX: str = "/api/v1"
    
    # Application metadata
    APP_NAME: str = "MetaView API"
    APP_VERSION: str = "1.0.0"
    
    # OpenAI API - REQUIRED in production
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is required in production")

    # Optional override for the OpenAI-compatible endpoint. Empty -> vendor
    # default. Point at a SubGate gateway's /v1 URL to route inference through
    # it; OPENAI_API_KEY then holds the SubGate consumer token instead of a
    # vendor key. Not required — an unset value keeps the direct-to-vendor path.
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")

    # Redis - REQUIRED in production
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    if not REDIS_URL:
        raise ValueError("REDIS_URL environment variable is required in production")
    
    # Cloudflare R2 - REQUIRED in production
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "")
    R2_PUBLIC_BASE_URL: str = os.getenv("R2_PUBLIC_BASE_URL", "")
    
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_BASE_URL]):
        raise ValueError("All R2 environment variables are required in production: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_BASE_URL")
    
    # Screenshot system uses Playwright (no API key needed)
    
    # Placeholder image fallback
    PLACEHOLDER_IMAGE_URL: str = os.getenv(
        "PLACEHOLDER_IMAGE_URL", 
        "https://via.placeholder.com/1200x630/2979FF/FFFFFF?text=Preview+Not+Available"
    )
    
    # Stripe - REQUIRED in production
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_TIER_BASIC: str = os.getenv("STRIPE_PRICE_TIER_BASIC", "")
    STRIPE_PRICE_TIER_PRO: str = os.getenv("STRIPE_PRICE_TIER_PRO", "")
    STRIPE_PRICE_TIER_AGENCY: str = os.getenv("STRIPE_PRICE_TIER_AGENCY", "")
    
    if not STRIPE_SECRET_KEY:
        raise ValueError("STRIPE_SECRET_KEY environment variable is required in production")
    if not STRIPE_WEBHOOK_SECRET:
        raise ValueError("STRIPE_WEBHOOK_SECRET environment variable is required in production")
    
    # Frontend URL - REQUIRED in production
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "")
    if not FRONTEND_URL:
        raise ValueError("FRONTEND_URL environment variable is required in production")
    
    # Maximum request body size (10MB)
    MAX_REQUEST_SIZE: int = int(os.getenv("MAX_REQUEST_SIZE", "10485760"))

    # Email / SMTP (Cloudflare Email Service). Optional — EMAIL_ENABLED=false disables sending.
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.mx.cloudflare.net")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER: str = os.getenv("SMTP_USER", "api_token")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "noreply@mymetaview.com")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "MyMetaView")

    # Browser Rendering offload (Cloudflare). Optional — off keeps local Playwright capture.
    BROWSER_RENDERING_ENABLED: bool = os.getenv("BROWSER_RENDERING_ENABLED", "false").lower() == "true"
    CF_ACCOUNT_ID: str = os.getenv("CF_ACCOUNT_ID", "")
    CF_BROWSER_RENDERING_TOKEN: str = os.getenv("CF_BROWSER_RENDERING_TOKEN", "")
    # Safety cap: stop using remote rendering past this many browser-seconds/month
    # (10h free = 36000s; default 34200 = 9.5h leaves headroom before overage).
    BROWSER_RENDERING_MONTHLY_SECONDS_CAP: int = int(os.getenv("BROWSER_RENDERING_MONTHLY_SECONDS_CAP", "34200"))


# Export settings instance
production_settings = ProductionSettings()

