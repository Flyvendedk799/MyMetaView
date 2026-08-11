"""Authenticated preview generation runs (single and bulk).

Generates previews for one or many URLs in a background job and persists each as a
real ``Preview`` row on the account (unlike the demo batch, which is ephemeral).
Progress is streamed to Redis so the dashboard can show a live per-URL status list
— and a per-org index of recent runs lets that view survive a page reload / tab
close. Single-URL generations are tracked the same way (a run of one, ``kind
== "single"``), which is what lets the create-preview dialog close the moment the
job is queued instead of holding the user hostage until it finishes.

Each URL is run through the exact same proven path as a single generation
(``generate_preview_job``), so bulk gets brand settings, plan gating, a/b/c
variants, and dead-letter handling for free.

URLs are processed SEQUENTIALLY, in this job's own execution context — the same
context a normal single-URL job uses. This is deliberate: the screenshot stage
drives Playwright's *sync* API, whose objects are greenlet/thread-bound, so
capturing from several worker threads at once raises "cannot switch to a
different thread". Sequential keeps each capture in one thread and correct.
(Concurrency across DIFFERENT bulk runs / users comes from running multiple
worker processes — see backend/queue/worker.py — not from threads in here.)
"""
import json
import logging
from typing import Any, Dict, List, Optional

from backend.queue.queue_connection import get_redis_connection
from backend.jobs.preview_pipeline import generate_preview_job

logger = logging.getLogger("bulk_preview_worker")

BATCH_PREFIX = "saas:batch:"
BATCH_TTL = 172800  # 48 hours
ORG_INDEX_PREFIX = "saas:batches:org:"
ORG_INDEX_TTL = 172800  # 48 hours
ORG_INDEX_MAX = 20  # keep the last N batches per org


def _batch_key(batch_id: str) -> str:
    return f"{BATCH_PREFIX}{batch_id}"


def _org_index_key(organization_id: int) -> str:
    return f"{ORG_INDEX_PREFIX}{organization_id}"


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


def record_batch_for_org(organization_id: int, batch_id: str) -> None:
    """Add a batch id to the org's recent-batches index (newest first)."""
    try:
        redis_client = get_redis_connection()
        key = _org_index_key(organization_id)
        redis_client.lrem(key, 0, batch_id)  # avoid dupes
        redis_client.lpush(key, batch_id)
        redis_client.ltrim(key, 0, ORG_INDEX_MAX - 1)
        redis_client.expire(key, ORG_INDEX_TTL)
    except Exception as e:
        logger.warning("failed to index batch %s for org %s: %s", batch_id, organization_id, e)


def list_org_batches(organization_id: int, limit: int = ORG_INDEX_MAX) -> List[Dict[str, Any]]:
    """Return recent batch summaries for an org (newest first), skipping expired ones."""
    try:
        redis_client = get_redis_connection()
        ids = redis_client.lrange(_org_index_key(organization_id), 0, limit - 1)
    except Exception as e:
        logger.warning("failed to list batches for org %s: %s", organization_id, e)
        return []
    out: List[Dict[str, Any]] = []
    for bid in ids or []:
        data = get_bulk_batch_data(bid)
        if not data:
            continue
        # Summary only — omit the (potentially large) per-URL results list here.
        out.append({
            "batch_id": data.get("batch_id", bid),
            "status": data.get("status"),
            "domain": data.get("domain"),
            "total": data.get("total", 0),
            "completed": data.get("completed", 0),
            "failed": data.get("failed", 0),
            "created_at": data.get("created_at"),
            "kind": data.get("kind", "bulk"),
            "label": data.get("label"),
        })
    return out


def _write_status(
    redis_client,
    batch_id: str,
    status: str,
    total: int,
    completed: int,
    failed: int,
    results: List[Dict[str, Any]],
    domain: Optional[str] = None,
    created_at: Optional[str] = None,
    kind: str = "bulk",
    label: Optional[str] = None,
) -> None:
    payload = {
        "batch_id": batch_id,
        "status": status,
        "domain": domain,
        "created_at": created_at,
        "kind": kind,          # "single" | "bulk" — drives how the run is labelled
        "label": label,        # e.g. the URL for a single-page run
        "total": total,
        "completed": completed,
        "failed": failed,
        "results": results,
    }
    redis_client.setex(_batch_key(batch_id), BATCH_TTL, json.dumps(payload))


def seed_batch(
    batch_id: str,
    organization_id: int,
    domain: str,
    total: int,
    created_at: str,
    kind: str = "bulk",
    label: Optional[str] = None,
) -> None:
    """Write an initial 'queued' record + index it so the run is visible at once,
    even before a worker picks it up (e.g. while all bulk workers are busy)."""
    try:
        redis_client = get_redis_connection()
        _write_status(
            redis_client, batch_id, "queued", total, 0, 0, [], domain, created_at, kind, label
        )
        record_batch_for_org(organization_id, batch_id)
    except Exception as e:
        logger.warning("failed to seed batch %s: %s", batch_id, e)


def fail_seeded_batch(batch_id: str, error: str) -> None:
    """Mark a seeded run as failed (used when enqueueing it never succeeded), so it
    doesn't sit in the activity list as 'queued' until the record expires."""
    data = get_bulk_batch_data(batch_id)
    if not data:
        return
    try:
        redis_client = get_redis_connection()
        _write_status(
            redis_client,
            batch_id,
            "failed",
            data.get("total", 0),
            0,
            data.get("total", 0),
            [{
                "url": data.get("label") or data.get("domain") or "",
                "status": "failed",
                "preview_id": None,
                "title": None,
                "image_url": None,
                "error": error[:400],
            }],
            data.get("domain"),
            data.get("created_at"),
            data.get("kind", "bulk"),
            data.get("label"),
        )
    except Exception as e:
        logger.warning("failed to mark batch %s as failed: %s", batch_id, e)


def generate_bulk_preview_job(
    batch_id: str,
    user_id: int,
    organization_id: int,
    domain: str,
    urls: List[str],
    force_regenerate: bool = False,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Background job: generate + persist previews for ``urls`` under ``domain``."""
    redis_client = get_redis_connection()
    total = len(urls)
    completed = 0
    failed = 0
    results: List[Dict[str, Any]] = []

    _write_status(redis_client, batch_id, "running", total, 0, 0, [], domain, created_at, "bulk")
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
        _write_status(
            redis_client, batch_id, "running", total, completed, failed, results, domain, created_at, "bulk"
        )

    final_status = "completed" if completed > 0 else "failed"
    _write_status(
        redis_client, batch_id, final_status, total, completed, failed, results, domain, created_at, "bulk"
    )
    logger.info("bulk %s: done. completed=%d failed=%d", batch_id, completed, failed)

    return {
        "batch_id": batch_id,
        "status": final_status,
        "total": total,
        "completed": completed,
        "failed": failed,
    }


def generate_tracked_preview_job(
    batch_id: str,
    user_id: int,
    organization_id: int,
    url: str,
    domain: str,
    force_regenerate: bool = False,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Background job: generate ONE preview, reporting progress as a run of one.

    Same work as ``generate_preview_job`` — this only adds the Redis run record the
    dashboard polls, so a single generation shows up in the activity list and keeps
    going after the tab that started it is closed.

    Failures are recorded on the run AND re-raised, so ``/jobs/{id}/status`` still
    reports the RQ job as failed with its error.
    """
    try:
        redis_client = get_redis_connection()
    except Exception as e:  # Redis down — the preview itself can still be generated
        logger.warning("single %s: no redis for progress (%s); generating untracked", batch_id, e)
        return generate_preview_job(user_id, organization_id, url, domain, force_regenerate=force_regenerate)

    _write_status(redis_client, batch_id, "running", 1, 0, 0, [], domain, created_at, "single", url)
    try:
        result = generate_preview_job(
            user_id, organization_id, url, domain, force_regenerate=force_regenerate
        )
    except Exception as e:  # already recorded to DLQ inside generate_preview_job
        logger.warning("single %s: failed %s: %s", batch_id, url[:80], e)
        item = {
            "url": url,
            "status": "failed",
            "preview_id": None,
            "title": None,
            "image_url": None,
            "error": str(e)[:400],
        }
        _write_status(
            redis_client, batch_id, "failed", 1, 0, 1, [item], domain, created_at, "single", url
        )
        raise

    preview = result.get("preview", {}) if isinstance(result, dict) else {}
    item = {
        "url": url,
        "status": "finished",
        "preview_id": result.get("preview_id") if isinstance(result, dict) else None,
        "title": preview.get("title"),
        "image_url": preview.get("image_url"),
        "error": None,
    }
    _write_status(
        redis_client, batch_id, "completed", 1, 1, 0, [item], domain, created_at, "single", url
    )
    return result
