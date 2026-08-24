"""Persisting traces where the admin panel can actually read them.

``JobTraceStore``'s default backend is an in-process LRU. That is fine for a
test and useless in production: previews are generated in RQ workers and the
admin panel runs in the web process, so every trace the operator wants to read
lives in a different process's memory. "Which fallbacks fired and why" was
answerable only by tailing worker logs.

This wires the store to Redis — one key per trace, plus a capped recent-jobs
list so the panel can show the last N generations without scanning. Redis being
unavailable falls back to the LRU, because a missing trace must never fail a
generation.

Call ``install()`` from the worker and web entry points; it is idempotent.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.services.preview.observability.job_trace import JobTraceStore

logger = logging.getLogger(__name__)

TRACE_KEY = "pv:trace:{job_id}"
RECENT_KEY = "pv:trace:recent"

# A trace is a debugging artefact, not a record. Two days is long enough to
# investigate a complaint and short enough that the keys never accumulate.
TRACE_TTL_S = 48 * 3600
RECENT_MAX = 500

_installed = False


def _redis():
    try:
        from backend.services.preview_cache import get_redis_client

        return get_redis_client()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Redis unavailable for trace store: %s", exc)
        return None


def _write(payload: Dict[str, Any]) -> None:
    client = _redis()
    if client is None:
        return
    job_id = payload.get("job_id")
    if not job_id:
        return
    try:
        body = json.dumps(payload, default=str)
        pipe = client.pipeline()
        pipe.setex(TRACE_KEY.format(job_id=job_id), TRACE_TTL_S, body)
        pipe.lpush(RECENT_KEY, job_id)
        pipe.ltrim(RECENT_KEY, 0, RECENT_MAX - 1)
        pipe.expire(RECENT_KEY, TRACE_TTL_S)
        pipe.execute()
    except Exception as exc:  # noqa: BLE001 — tracing never breaks a generation
        logger.debug("Trace write failed for %s: %s", job_id, exc)


def _read(job_id: str) -> Optional[Dict[str, Any]]:
    client = _redis()
    if client is None:
        return None
    try:
        raw = client.get(TRACE_KEY.format(job_id=job_id))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Trace read failed for %s: %s", job_id, exc)
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def recent(limit: int = 25) -> List[Dict[str, Any]]:
    """The last N traces, newest first, across every worker.

    Falls back to the in-process LRU so a dev machine without Redis still shows
    what it generated.
    """
    client = _redis()
    if client is None:
        return JobTraceStore.get_instance().list_recent(limit=limit)

    try:
        job_ids = client.lrange(RECENT_KEY, 0, max(0, limit - 1)) or []
    except Exception as exc:  # noqa: BLE001
        logger.debug("Recent trace listing failed: %s", exc)
        return JobTraceStore.get_instance().list_recent(limit=limit)

    out: List[Dict[str, Any]] = []
    for job_id in job_ids:
        payload = _read(job_id if isinstance(job_id, str) else job_id.decode())
        if payload:
            out.append(payload)
    return out or JobTraceStore.get_instance().list_recent(limit=limit)


def install() -> bool:
    """Point the trace store at Redis. Idempotent; safe when Redis is absent."""
    global _installed
    if _installed:
        return True
    JobTraceStore.get_instance().set_backend(writer=_write, reader=_read)
    _installed = True
    logger.info("JobTrace store backed by Redis (ttl=%dh, recent=%d)",
                TRACE_TTL_S // 3600, RECENT_MAX)
    return True
