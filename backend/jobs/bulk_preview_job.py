"""Authenticated bulk preview generation.

Generates previews for many URLs in one background job and persists each as a real
``Preview`` row on the account (unlike the demo batch, which is ephemeral). Progress
is streamed to Redis so the dashboard can show a live per-URL status list.

Each URL is run through the exact same proven path as a single generation
(``generate_preview_job``), so bulk gets brand settings, plan gating, a/b/c
variants, and dead-letter handling for free.
"""
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from backend.queue.queue_connection import get_redis_connection
from backend.jobs.preview_pipeline import generate_preview_job

logger = logging.getLogger("bulk_preview_worker")

BATCH_PREFIX = "saas:batch:"
BATCH_TTL = 86400  # 24 hours


def _get_max_workers() -> int:
    """Parallel URLs per bulk job. Kept modest — each preview spins up Chromium."""
    try:
        return max(1, min(6, int(os.environ.get("BULK_PREVIEW_MAX_WORKERS", "3"))))
    except (TypeError, ValueError):
        return 3


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


def _process_one(
    index: int,
    user_id: int,
    organization_id: int,
    url: str,
    domain: str,
    force_regenerate: bool,
) -> tuple[int, Dict[str, Any]]:
    """Generate one preview in a worker thread. Never raises to the pool."""
    try:
        result = generate_preview_job(
            user_id, organization_id, url, domain, force_regenerate=force_regenerate
        )
        preview = result.get("preview", {}) if isinstance(result, dict) else {}
        return index, {
            "url": url,
            "status": "finished",
            "preview_id": result.get("preview_id") if isinstance(result, dict) else None,
            "title": preview.get("title"),
            "image_url": preview.get("image_url"),
            "error": None,
        }
    except Exception as e:  # already recorded to DLQ inside generate_preview_job
        logger.warning("bulk: url failed %s: %s", url[:80], e)
        return index, {
            "url": url,
            "status": "failed",
            "preview_id": None,
            "title": None,
            "image_url": None,
            "error": str(e)[:400],
        }


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
    results_by_index: List[Optional[Dict[str, Any]]] = [None] * total
    lock = threading.RLock()

    _write_status(redis_client, batch_id, "running", total, 0, 0, [])
    logger.info("bulk %s: starting %d urls for org %s / %s", batch_id, total, organization_id, domain)

    workers = min(_get_max_workers(), total) if total > 0 else 1
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _process_one, i, user_id, organization_id, url, domain, force_regenerate
            ): i
            for i, url in enumerate(urls)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                _, item = future.result()
            except Exception as e:  # defensive — _process_one shouldn't raise
                item = {
                    "url": urls[idx],
                    "status": "failed",
                    "preview_id": None,
                    "title": None,
                    "image_url": None,
                    "error": str(e)[:400],
                }
            with lock:
                results_by_index[idx] = item
                if item.get("error") is None:
                    completed += 1
                else:
                    failed += 1
                ordered = [r for r in results_by_index if r is not None]
                _write_status(redis_client, batch_id, "running", total, completed, failed, ordered)

    results = [
        results_by_index[i]
        or {
            "url": urls[i],
            "status": "failed",
            "preview_id": None,
            "title": None,
            "image_url": None,
            "error": "Skipped",
        }
        for i in range(total)
    ]
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
