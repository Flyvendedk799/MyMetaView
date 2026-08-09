"""Authenticated bulk preview generation.

Generates previews for many URLs in one background job and persists each as a real
``Preview`` row on the account (unlike the demo batch, which is ephemeral). Progress
is streamed to Redis so the dashboard can show a live per-URL status list.

Each URL is run through the exact same proven path as a single generation
(``generate_preview_job``), so bulk gets brand settings, plan gating, a/b/c
variants, and dead-letter handling for free.

URLs are processed SEQUENTIALLY, in this job's own execution context — the same
context a normal single-URL job uses. This is deliberate: the screenshot stage
drives Playwright's *sync* API, whose objects are greenlet/thread-bound, so
capturing from several worker threads at once raises "cannot switch to a
different thread". Sequential keeps each capture in one thread and correct.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from backend.queue.queue_connection import get_redis_connection
from backend.jobs.preview_pipeline import generate_preview_job

logger = logging.getLogger("bulk_preview_worker")

BATCH_PREFIX = "saas:batch:"
BATCH_TTL = 86400  # 24 hours


def _batch_key(batch_id: str) -> str:
    return f"{BATCH_PREFIX}{batch_id}"


def get_bulk_batch_data(batch_id: str) -> Optional[Dict[str, Any]]:
    """Load a bulk batch's status/results from Redis. None if unknown/expired."""
    try:
        redis_client = get_redis_connection()
        raw = redis_client.get(_batch_key(batch_id))
    except Exception as e:  # Redis down — surface as "not found" to the route
        logger.warning("bulk batch read failed for %s: %s", batch_id, e)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _write_status(
    redis_client,
    batch_id: str,
    status: str,
    total: int,
    completed: int,
    failed: int,
    results: List[Dict[str, Any]],
) -> None:
    payload = {
        "batch_id": batch_id,
        "status": status,
        "total": total,
        "completed": completed,
        "failed": failed,
        "results": results,
    }
    redis_client.setex(_batch_key(batch_id), BATCH_TTL, json.dumps(payload))


def generate_bulk_preview_job(
    batch_id: str,
    user_id: int,
    organization_id: int,
    domain: str,
    urls: List[str],
    force_regenerate: bool = False,
) -> Dict[str, Any]:
    """Background job: generate + persist previews for ``urls`` under ``domain``."""
    redis_client = get_redis_connection()
    total = len(urls)
    completed = 0
    failed = 0
    results: List[Dict[str, Any]] = []

    _write_status(redis_client, batch_id, "running", total, 0, 0, [])
    logger.info("bulk %s: starting %d urls for org %s / %s", batch_id, total, organization_id, domain)

    for url in urls:
        try:
            result = generate_preview_job(
                user_id, organization_id, url, domain, force_regenerate=force_regenerate
            )
            preview = result.get("preview", {}) if isinstance(result, dict) else {}
            item = {
                "url": url,
                "status": "finished",
                "preview_id": result.get("preview_id") if isinstance(result, dict) else None,
                "title": preview.get("title"),
                "image_url": preview.get("image_url"),
                "error": None,
            }
            completed += 1
        except Exception as e:  # already recorded to DLQ inside generate_preview_job
            logger.warning("bulk %s: url failed %s: %s", batch_id, url[:80], e)
            item = {
                "url": url,
                "status": "failed",
                "preview_id": None,
                "title": None,
                "image_url": None,
                "error": str(e)[:400],
            }
            failed += 1

        results.append(item)
        # Stream progress after each URL so the dashboard updates live.
        _write_status(redis_client, batch_id, "running", total, completed, failed, results)

    final_status = "completed" if completed > 0 else "failed"
    _write_status(redis_client, batch_id, final_status, total, completed, failed, results)
    logger.info("bulk %s: done. completed=%d failed=%d", batch_id, completed, failed)

    return {
        "batch_id": batch_id,
        "status": final_status,
        "total": total,
        "completed": completed,
        "failed": failed,
    }
