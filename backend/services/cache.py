"""Redis-based caching service for hot data."""
import json
import logging
from typing import Optional, Any
from backend.queue.queue_connection import get_redis_connection
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Cache TTLs (in seconds)
BRAND_SETTINGS_TTL = 300  # 5 minutes
DOMAIN_TTL = 180  # 3 minutes
PREVIEW_METADATA_TTL = 300  # 5 minutes


def _get_cache_key(prefix: str, *args) -> str:
    """Generate cache key from prefix and arguments."""
    return f"cache:{prefix}:{':'.join(str(arg) for arg in args)}"


def _serialize(value: Any) -> str:
    """Serialize value to JSON string."""
    return json.dumps(value, default=str)


def _deserialize(value: str) -> Any:
    """Deserialize JSON string to value."""
    return json.loads(value)


def _brand_settings_key(org_id: int, domain_id: Optional[int] = None) -> str:
    """Brands are per domain; domain_id None is the organization-wide default."""
    return _get_cache_key("brand_settings", org_id, domain_id if domain_id is not None else "org")


def get_cached_brand_settings(org_id: int, domain_id: Optional[int] = None) -> Optional[dict]:
    """Get cached brand settings for an organization's domain."""
    try:
        redis_client = get_redis_connection()
        cached = redis_client.get(_brand_settings_key(org_id, domain_id))
        if cached:
            return _deserialize(cached)
    except Exception as e:
        logger.warning(f"Cache get error for brand_settings:{org_id}:{domain_id}: {e}")
    return None


def set_cached_brand_settings(org_id: int, value: dict, domain_id: Optional[int] = None) -> None:
    """Cache brand settings for an organization's domain."""
    try:
        redis_client = get_redis_connection()
        redis_client.setex(
            _brand_settings_key(org_id, domain_id), BRAND_SETTINGS_TTL, _serialize(value)
        )
    except Exception as e:
        logger.warning(f"Cache set error for brand_settings:{org_id}:{domain_id}: {e}")


def invalidate_brand_settings(org_id: int, domain_id: Optional[int] = None) -> None:
    """Invalidate cached brand settings for an organization's domain."""
    try:
        redis_client = get_redis_connection()
        redis_client.delete(_brand_settings_key(org_id, domain_id))
    except Exception as e:
        logger.warning(f"Cache invalidate error for brand_settings:{org_id}:{domain_id}: {e}")


def get_cached_domain_by_name(org_id: int, domain_name: str) -> Optional[dict]:
    """Get cached domain by organization ID and domain name."""
    try:
        redis_client = get_redis_connection()
        key = _get_cache_key("domain", org_id, domain_name)
        cached = redis_client.get(key)
        if cached:
            return _deserialize(cached)
    except Exception as e:
        logger.warning(f"Cache get error for domain:{org_id}:{domain_name}: {e}")
    return None


def set_cached_domain_by_name(org_id: int, domain_name: str, value: dict) -> None:
    """Cache domain by organization ID and domain name."""
    try:
        redis_client = get_redis_connection()
        key = _get_cache_key("domain", org_id, domain_name)
        redis_client.setex(key, DOMAIN_TTL, _serialize(value))
    except Exception as e:
        logger.warning(f"Cache set error for domain:{org_id}:{domain_name}: {e}")


def invalidate_domain(org_id: int, domain_name: str) -> None:
    """Invalidate cached domain by organization ID and domain name."""
    try:
        redis_client = get_redis_connection()
        key = _get_cache_key("domain", org_id, domain_name)
        redis_client.delete(key)
        # Also invalidate all domains for this org (pattern match)
        pattern = _get_cache_key("domain", org_id, "*")
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)
    except Exception as e:
        logger.warning(f"Cache invalidate error for domain:{org_id}:{domain_name}: {e}")


def get_cached_preview_metadata(preview_id: int) -> Optional[dict]:
    """Get cached preview metadata by preview ID."""
    try:
        redis_client = get_redis_connection()
        key = _get_cache_key("preview_metadata", preview_id)
        cached = redis_client.get(key)
        if cached:
            return _deserialize(cached)
    except Exception as e:
        logger.warning(f"Cache get error for preview_metadata:{preview_id}: {e}")
    return None


def set_cached_preview_metadata(preview_id: int, value: dict) -> None:
    """Cache preview metadata by preview ID."""
    try:
        redis_client = get_redis_connection()
        key = _get_cache_key("preview_metadata", preview_id)
        redis_client.setex(key, PREVIEW_METADATA_TTL, _serialize(value))
    except Exception as e:
        logger.warning(f"Cache set error for preview_metadata:{preview_id}: {e}")


def invalidate_preview(preview_id: int) -> None:
    """Invalidate cached preview metadata by preview ID."""
    try:
        redis_client = get_redis_connection()
        key = _get_cache_key("preview_metadata", preview_id)
        redis_client.delete(key)
    except Exception as e:
        logger.warning(f"Cache invalidate error for preview_metadata:{preview_id}: {e}")

