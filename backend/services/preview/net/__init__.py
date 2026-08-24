"""Outbound HTTP for the preview engine — one session, one safety policy.

Everything the engine fetches is influenced by a URL a user typed: the page
itself, the images on it, an uploaded logo, a favicon href. Before this package
each of those was a bare ``requests.get`` with its own timeout, no retry, no
shared connection pool, and — the part that matters — no check that the host
resolves somewhere we are allowed to reach. The engine runs inside the
infrastructure network, so "fetch this URL" was a request to reach the metadata
service or a private box if the caller asked nicely.

Two exports carry the policy:

  ``guard_url``   — resolves the host and refuses private/link-local/loopback
                    addresses, non-HTTP schemes, and bad ports.
  ``fetch``       — a pooled, retrying GET that guards every hop, including the
                    ones a redirect introduces.

Use them for every outbound request. ``fetch_many`` runs a batch concurrently,
which is what turns a page's dozen logo candidates from serial round-trips into
one wait.
"""

from backend.services.preview.net.session import (
    BROWSER_HEADERS,
    FetchResult,
    fetch,
    fetch_many,
    get_session,
)
from backend.services.preview.net.ssrf import (
    SSRFError,
    UrlPolicy,
    guard_url,
    is_public_host,
)

__all__ = [
    "BROWSER_HEADERS",
    "FetchResult",
    "SSRFError",
    "UrlPolicy",
    "fetch",
    "fetch_many",
    "get_session",
    "guard_url",
    "is_public_host",
]
