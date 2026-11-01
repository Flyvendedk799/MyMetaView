"""Token generation and verification for weekly digest unsubscribe links."""
import base64
import hashlib
import hmac
import time
from typing import Tuple, Optional
from backend.core.config import settings


def generate_digest_unsubscribe_token(email: str, timestamp: Optional[int] = None) -> str:
    """Generate a signed, expiring token for weekly digest one-click unsubscribe.

    Args:
        email: The recipient's email address.
        timestamp: Optional UNIX timestamp (defaults to current time).

    Returns:
        URL-safe string token.
    """
    ts = timestamp if timestamp is not None else int(time.time())
    normalized_email = email.lower().strip()
    msg = f"{normalized_email}:{ts}:weekly_digest_unsubscribe".encode("utf-8")
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    raw = f"{normalized_email}|{ts}|{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def verify_digest_unsubscribe_token(
    token: str, max_age_seconds: int = 30 * 86400
) -> Tuple[bool, Optional[str], str]:
    """Verify signed unsubscribe token.

    Args:
        token: The token received in the query parameter.
        max_age_seconds: Maximum allowed age in seconds (default: 30 days).

    Returns:
        A tuple of (is_valid, email, status_reason).
        status_reason is one of: 'valid', 'expired', 'tampered', 'invalid'.
    """
    if not token or not isinstance(token, str):
        return False, None, "invalid"

    try:
        raw_bytes = base64.urlsafe_b64decode(token.encode("utf-8"))
        raw = raw_bytes.decode("utf-8")
        parts = raw.split("|")
        if len(parts) != 3:
            return False, None, "invalid"
        email, ts_str, sig = parts
        ts = int(ts_str)
    except Exception:
        return False, None, "invalid"

    normalized_email = email.lower().strip()
    msg = f"{normalized_email}:{ts}:weekly_digest_unsubscribe".encode("utf-8")
    expected_sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, sig):
        return False, None, "tampered"

    current_time = int(time.time())
    if current_time - ts > max_age_seconds:
        return False, normalized_email, "expired"

    # Reject timestamps more than 5 minutes into the future
    if ts > current_time + 300:
        return False, None, "tampered"

    return True, normalized_email, "valid"
