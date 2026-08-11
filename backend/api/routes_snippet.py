"""Serving for the embed snippet itself.

The snippet is a static asset, but it is *the* integration surface: it is loaded
from every customer page, on every page view. That earns it explicit control
over caching, CORS and revalidation rather than the defaults a static mount
gives.

Three paths serve the same file:
  /snippet.js         the canonical URL
  /s.js               a short alias, for hand-typed and character-limited fields
  /static/snippet.js  the original URL, kept working for existing installs
"""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["snippet"])

SNIPPET_FILE = Path(__file__).resolve().parent.parent / "static" / "snippet.js"

# An hour is short enough that a fix reaches customers the same day, long enough
# that the file is not re-fetched on every page view.
CACHE_CONTROL = "public, max-age=3600, stale-while-revalidate=86400"


@lru_cache(maxsize=1)
def _snippet() -> tuple[bytes, str]:
    """Read the snippet once and derive its ETag."""
    body = SNIPPET_FILE.read_bytes()
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    return body, etag


def _serve(request: Request) -> Response:
    try:
        body, etag = _snippet()
    except OSError:
        logger.error("Snippet file is missing at %s", SNIPPET_FILE)
        # Serve a valid, inert script: a 404 in the console on a customer's site
        # is worse than a no-op.
        return Response(
            content=b"/* MyMetaView snippet unavailable */\n",
            media_type="application/javascript; charset=utf-8",
            headers={"Cache-Control": "no-store", "Access-Control-Allow-Origin": "*"},
        )

    headers = {
        "Cache-Control": CACHE_CONTROL,
        "ETag": etag,
        # Loaded cross-origin from every customer site.
        "Access-Control-Allow-Origin": "*",
        "Timing-Allow-Origin": "*",
        "X-Content-Type-Options": "nosniff",
    }

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return Response(
        content=body,
        media_type="application/javascript; charset=utf-8",
        headers=headers,
    )


@router.get("/snippet.js", include_in_schema=False)
def get_snippet(request: Request) -> Response:
    return _serve(request)


@router.get("/s.js", include_in_schema=False)
def get_snippet_short(request: Request) -> Response:
    return _serve(request)


@router.get("/static/snippet.js", include_in_schema=False)
def get_snippet_legacy(request: Request) -> Response:
    """The URL shipped before /snippet.js existed. Still live on customer sites."""
    return _serve(request)
