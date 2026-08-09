"""Configuration settings for the FastAPI backend."""
import os
import secrets
from typing import List

# Install the LLM-gateway param-compat shim as early as possible. Every AI
# service imports `settings` from here before it constructs an OpenAI client, so
# importing this module guarantees the shim is in place before any chat request
# (it drops `temperature`/`seed`, which the gateway's Anthropic model 400s on).
try:  # never let a shim import break config loading
    from backend.services import openai_compat  # noqa: F401
except Exception:
    pass

# Check if we're in production mode
ENV = os.getenv("ENV", "development").lower()

# Import production settings if in production
if ENV == "production":
    try:
        from backend.settings.production import production_settings
        _use_production = True
    except ImportError:
        _use_production = False
else:
    _use_production = False


class Settings:
    """Application settings."""
    
    # Database URL - defaults to SQLite for local development
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./app.db"  # SQLite file in project root
    )
    
    # Security settings
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        secrets.token_urlsafe(32) if ENV != "production" else ""  # No fallback in production
    )
    ALGORITHM: str = "HS256"
    # Production: 7 days, Development: 60 minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60 if ENV == "production" else 60
    
    # CORS allowed origins
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",  # Vite default dev server
        "http://localhost:3000",  # Alternative React dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    
    # API version
    API_V1_PREFIX: str = "/api/v1"
    
    # Application metadata
    APP_NAME: str = "MetaView API"
    APP_VERSION: str = "1.0.0"
    
    # OpenAI API configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # Optional override for the OpenAI-compatible endpoint. Empty -> the vendor
    # default (https://api.openai.com/v1). Set to a SubGate gateway's /v1 URL to
    # route inference through it; the OpenAI SDK reads base_url from here, so no
    # other code changes. OPENAI_API_KEY then becomes the SubGate consumer token.
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")

    # Redis configuration for job queue
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Cloudflare R2 configuration
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "")
    R2_PUBLIC_BASE_URL: str = os.getenv("R2_PUBLIC_BASE_URL", "")
    
    # Screenshot system uses Playwright (no API key needed)
    
    # Placeholder image fallback
    PLACEHOLDER_IMAGE_URL: str = os.getenv("PLACEHOLDER_IMAGE_URL", "https://via.placeholder.com/1200x630/2979FF/FFFFFF?text=Preview+Not+Available")
    
    # Stripe configuration
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_TIER_BASIC: str = os.getenv("STRIPE_PRICE_TIER_BASIC", "")
    STRIPE_PRICE_TIER_PRO: str = os.getenv("STRIPE_PRICE_TIER_PRO", "")
    STRIPE_PRICE_TIER_AGENCY: str = os.getenv("STRIPE_PRICE_TIER_AGENCY", "")
    
    # Frontend URL for invite links
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # CORS allowed origins (comma-separated list)
    CORS_ALLOWED_ORIGINS: str = os.getenv("CORS_ALLOWED_ORIGINS", "")
    
    # Maximum request body size (in bytes, default 10MB)
    MAX_REQUEST_SIZE: int = int(os.getenv("MAX_REQUEST_SIZE", "10485760"))  # 10MB

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


# Use production settings if available, otherwise use default Settings
if _use_production:
    settings = production_settings
else:
    settings = Settings()

