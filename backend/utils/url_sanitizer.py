"""URL sanitization and validation utilities."""
from urllib.parse import urlparse, urlunparse
from backend.core.config import settings

# Maximum URL length (2048 characters as per HTTP spec)
MAX_URL_LENGTH = 2048

# Dangerous URL schemes to block
DANGEROUS_SCHEMES = {
    'javascript:', 'data:', 'file:', 'vbscript:', 'about:', 'chrome:', 
    'chrome-extension:', 'moz-extension:', 'edge:', 'ms-browser-extension:'
}


def validate_url_security(url: str) -> None:
    """
    Validate URL security - block dangerous schemes and enforce length limits.
    
    Args:
        url: URL to validate
        
    Raises:
        ValueError: If URL is invalid or dangerous
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    
    # Check length
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"URL exceeds maximum length of {MAX_URL_LENGTH} characters")
    
    # Strip whitespace for scheme checking
    url_stripped = url.strip()
    url_lower = url_stripped.lower()
    
    # Block dangerous schemes
    for dangerous_scheme in DANGEROUS_SCHEMES:
        if url_lower.startswith(dangerous_scheme):
            raise ValueError(f"Invalid URL scheme: {dangerous_scheme} URLs are not allowed")
    
    # Parse and validate scheme
    try:
        parsed = urlparse(url_stripped)
        if parsed.scheme and parsed.scheme.lower() not in ['http', 'https']:
            raise ValueError(f"Invalid URL scheme: only http and https are allowed")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Invalid URL format: {str(e)}")


def normalize_url_for_cache(url: str) -> str:
    """
    Normalize URL for deterministic cache key generation.
    
    This ensures the same URL always produces the same cache key, regardless of:
    - Trailing slashes
    - www vs non-www
    - http vs https
    - Fragments and recognized tracking query parameters

    Preserve path case and content-selecting query parameters.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL string
    """
    if not url or not isinstance(url, str):
        return ""
    
    from backend.services.site_coverage import page_identity
    parsed = urlparse(page_identity(url.strip()))
    return urlunparse(parsed._replace(scheme="https", netloc=parsed.netloc.removeprefix("www.")))



def sanitize_url(url: str, domain: str = None) -> str:
    """
    Sanitize and validate URL before preview generation.
    
    Args:
        url: URL to sanitize
        domain: Expected domain name (for validation, optional)
        
    Returns:
        Sanitized URL string
        
    Raises:
        ValueError: If URL is invalid or doesn't match domain
    """
    # Security validation first
    validate_url_security(url)
    
    # Strip whitespace
    url = url.strip()
    
    # Parse URL
    parsed = urlparse(url)
    
    # Ensure HTTPS (convert HTTP to HTTPS)
    if parsed.scheme == "http":
        parsed = parsed._replace(scheme="https")
    elif not parsed.scheme:
        # If no scheme, assume HTTPS
        parsed = parsed._replace(scheme="https")
    
    # Remove fragment (#)
    parsed = parsed._replace(fragment="")
    
    # Normalize trailing slash (remove for consistency)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/"
    parsed = parsed._replace(path=path)
    
    # Reconstruct URL
    sanitized_url = urlunparse(parsed)
    
    # Validate domain matches if domain provided
    if domain:
        parsed_sanitized = urlparse(sanitized_url)
        hostname = parsed_sanitized.netloc
        
        # Remove port if present
        if ':' in hostname:
            hostname = hostname.split(':')[0]
        
        # Remove www. prefix for comparison
        hostname_normalized = hostname[4:] if hostname.startswith('www.') else hostname
        domain_normalized = domain[4:] if domain.startswith('www.') else domain
        
        if hostname_normalized.lower() != domain_normalized.lower():
            raise ValueError(f"URL domain '{hostname_normalized}' does not match expected domain '{domain_normalized}'")
    
    return sanitized_url

