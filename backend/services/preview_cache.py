"""
Preview caching service for AI visual focus system.

Provides URL-based caching to:
- Avoid redundant AI calls for the same URL
- Reduce costs and latency
- Provide consistent results for identical URLs
"""
import json
import hashlib
import logging
import os
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import redis
from backend.core.config import settings

logger = logging.getLogger("preview_worker")


# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

class CacheConfig:
    """Cache configuration settings."""
    # Cache TTL (time to live)
    DEFAULT_TTL_HOURS: int = 24
    MAX_TTL_HOURS: int = 168  # 7 days
    # Demo-specific TTL (configurable for 400% throughput - longer TTL = more cache hits)
    DEMO_TTL_HOURS: int = int(os.getenv("DEMO_CACHE_TTL_HOURS", "48"))
    
    # Cache key prefixes
    PREVIEW_PREFIX: str = "preview:focus:"
    ANALYSIS_PREFIX: str = "preview:analysis:"
    
    # Size limits
    MAX_CACHED_ANALYSIS_SIZE: int = 10000  # bytes


# =============================================================================
# CACHE KEY GENERATION
# =============================================================================

def generate_cache_key(url: str, prefix: str = CacheConfig.PREVIEW_PREFIX, version: str = "v1") -> str:
    """
    Generate a deterministic cache key for a URL.
    
    Uses normalized URL + version for consistent, fixed-length keys.
    This ensures same URL always produces same cache key.
    
    Args:
        url: URL to generate key for
        prefix: Cache key prefix
        version: Cache version (increment when breaking changes occur)
        
    Returns:
        Deterministic cache key
    """
    from backend.utils.url_sanitizer import normalize_url_for_cache
    
    # Normalize URL for deterministic hashing
    url_normalized = normalize_url_for_cache(url)
    
    # Create deterministic hash (URL + version)
    cache_string = f"{url_normalized}:{version}"
    url_hash = hashlib.md5(cache_string.encode()).hexdigest()
    
    return f"{prefix}{url_hash}"


# =============================================================================
# REDIS CLIENT
# =============================================================================

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client."""
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    if not settings.REDIS_URL:
        logger.warning("REDIS_URL not configured, caching disabled")
        return None
    
    try:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        # Test connection
        _redis_client.ping()
        logger.info("Redis cache connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis connection failed, caching disabled: {e}")
        return None


# =============================================================================
# CACHE OPERATIONS
# =============================================================================

def get_cached_analysis(url: str) -> Optional[Dict[str, Any]]:
    """
    Get cached AI analysis for a URL.
    
    Returns:
        Cached analysis dict or None if not found/expired
    """
    client = get_redis_client()
    if client is None:
        return None
    
    try:
        key = generate_cache_key(url, CacheConfig.ANALYSIS_PREFIX)
        data = client.get(key)
        
        if data:
            cached = json.loads(data)
            logger.debug(f"Cache hit for URL analysis: {url[:50]}...")
            return cached
        
        return None
        
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None


def cache_analysis(
    url: str, 
    analysis: Dict[str, Any],
    ttl_hours: int = CacheConfig.DEFAULT_TTL_HOURS
) -> bool:
    """
    Cache AI analysis for a URL.
    
    Args:
        url: Source URL
        analysis: Analysis result to cache
        ttl_hours: Cache TTL in hours
        
    Returns:
        True if cached successfully
    """
    client = get_redis_client()
    if client is None:
        return False
    
    try:
        key = generate_cache_key(url, CacheConfig.ANALYSIS_PREFIX)
        
        # Add cache metadata
        cache_data = {
            **analysis,
            "_cached_at": datetime.utcnow().isoformat(),
            "_url_hash": key.split(":")[-1]
        }
        
        data = json.dumps(cache_data)
        
        # Check size limit
        if len(data) > CacheConfig.MAX_CACHED_ANALYSIS_SIZE:
            logger.warning(f"Analysis too large to cache: {len(data)} bytes")
            return False
        
        # Set with TTL
        ttl_seconds = min(ttl_hours, CacheConfig.MAX_TTL_HOURS) * 3600
        client.setex(key, ttl_seconds, data)
        
        logger.debug(f"Cached analysis for URL: {url[:50]}...")
        return True
        
    except Exception as e:
        logger.warning(f"Cache write error: {e}")
        return False


def get_cached_preview_urls(url: str) -> Optional[Tuple[str, str]]:
    """
    Get cached preview image URLs for a source URL.
    
    Returns:
        Tuple of (main_image_url, highlight_image_url) or None
    """
    client = get_redis_client()
    if client is None:
        return None
    
    try:
        key = generate_cache_key(url, CacheConfig.PREVIEW_PREFIX)
        data = client.get(key)
        
        if data:
            cached = json.loads(data)
            logger.debug(f"Cache hit for preview URLs: {url[:50]}...")
            return (cached.get("main_url"), cached.get("highlight_url"))
        
        return None
        
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None


def cache_preview_urls(
    url: str,
    main_url: str,
    highlight_url: str,
    ttl_hours: int = CacheConfig.DEFAULT_TTL_HOURS
) -> bool:
    """
    Cache preview image URLs for a source URL.
    
    Args:
        url: Source URL
        main_url: Main screenshot URL
        highlight_url: Highlight image URL
        ttl_hours: Cache TTL in hours
        
    Returns:
        True if cached successfully
    """
    client = get_redis_client()
    if client is None:
        return False
    
    try:
        key = generate_cache_key(url, CacheConfig.PREVIEW_PREFIX)
        
        cache_data = {
            "main_url": main_url,
            "highlight_url": highlight_url,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        data = json.dumps(cache_data)
        ttl_seconds = min(ttl_hours, CacheConfig.MAX_TTL_HOURS) * 3600
        client.setex(key, ttl_seconds, data)
        
        logger.debug(f"Cached preview URLs for: {url[:50]}...")
        return True
        
    except Exception as e:
        logger.warning(f"Cache write error: {e}")
        return False


def invalidate_cache(url: str) -> bool:
    """
    Invalidate all cache entries for a URL across ALL prefixes.
    
    Call this when a preview needs to be regenerated.
    FIXED: Now clears all cache prefixes including demo caches.
    """
    client = get_redis_client()
    if client is None:
        return False
    
    try:
        # All possible cache prefixes used in the system. These must match the
        # prefixes callers actually pass to engine.generate(); a mismatch means
        # "regenerate" quietly serves the stale entry for its full TTL.
        all_prefixes = [
            CacheConfig.PREVIEW_PREFIX,   # "preview:focus:"
            CacheConfig.ANALYSIS_PREFIX,  # "analysis:"
            "demo:preview:",              # Demo route v1
            "demo:preview:v2:",           # Demo route v2 (job-based)
            "demo:preview:v3:fast:",      # Demo v3 quality profiles
            "demo:preview:v3:balanced:",
            "demo:preview:v3:ultra:",
            "demo:preview:v3:template:",  # Demo past its AI allowance
            "preview:engine:",            # Engine default
            "preview:enhanced:",          # Enhanced engine
            "saas:preview:",              # SaaS legacy (pre-lane)
            "saas:preview:ai:",           # SaaS AI lane (jobs/preview_pipeline)
            "saas:preview:template:",     # SaaS template lane
        ]
        
        keys = [generate_cache_key(url, prefix) for prefix in all_prefixes]
        
        deleted = client.delete(*keys)
        logger.info(f"Invalidated {deleted} cache entries for: {url[:50]}... (checked {len(keys)} prefixes)")
        return True
        
    except Exception as e:
        logger.warning(f"Cache invalidation error: {e}")
        return False


# =============================================================================
# CACHE STATISTICS
# =============================================================================

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring."""
    client = get_redis_client()
    if client is None:
        return {"enabled": False}
    
    try:
        info = client.info("stats")
        keyspace = client.info("keyspace")
        
        # Count preview-related keys
        preview_keys = len(list(client.scan_iter(f"{CacheConfig.PREVIEW_PREFIX}*", count=1000)))
        analysis_keys = len(list(client.scan_iter(f"{CacheConfig.ANALYSIS_PREFIX}*", count=1000)))
        
        return {
            "enabled": True,
            "preview_entries": preview_keys,
            "analysis_entries": analysis_keys,
            "total_hits": info.get("keyspace_hits", 0),
            "total_misses": info.get("keyspace_misses", 0),
            "memory_used": info.get("used_memory_human", "unknown")
        }
        
    except Exception as e:
        return {"enabled": True, "error": str(e)}


# =============================================================================
# ADMIN SETTINGS: DEMO CACHE CONTROL
# =============================================================================

def is_demo_cache_disabled() -> bool:
    """
    Check if demo caching is disabled via admin toggle.
    
    Returns:
        True if demo caching is disabled, False otherwise (defaults to False for fail-safe)
    """
    client = get_redis_client()
    if client is None:
        logger.debug("Redis not available, cache enabled (fail-safe)")
        return False  # Fail-safe: if Redis unavailable, allow caching
    
    try:
        key = "admin:settings:demo_cache_disabled"
        value = client.get(key)
        
        # Log the check for debugging
        logger.debug(f"Checking demo cache disabled: key={key}, value={value}, type={type(value)}")
        
        if value is None:
            logger.debug("Demo cache disabled setting not found, defaulting to enabled")
            return False  # Default: caching enabled
        
        # Handle both string and bytes values
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        
        disabled = str(value).lower() == "true"
        logger.info(f"Demo cache disabled check: value='{value}' -> disabled={disabled}")
        return disabled
    except Exception as e:
        logger.warning(f"Failed to check demo cache disable setting: {e}", exc_info=True)
        return False  # Fail-safe: allow caching if check fails
