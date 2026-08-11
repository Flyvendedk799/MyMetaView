"""
Background job for batch demo preview generation (MyMetaView 4.0 P3).
Processes multiple URLs in a single job, stores results in Redis.
P8: Webhooks on job completion (success or partial).

6.0 OPTIMIZATIONS (400% throughput):
- Parallel URL processing via ThreadPoolExecutor (4 workers)
- Throttled Redis writes (status every N completions or on final)
- Non-blocking webhook delivery (fire-and-forget)
"""
from typing import Dict, Any, List, Optional
from uuid import uuid4
import json
import logging
import os
import threading
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.services.preview_engine import PreviewEngine, PreviewEngineConfig
from backend.services.quality_profiles import get_quality_profile
from backend.services.preview_cache import (
    get_redis_client,
    is_demo_cache_disabled,
)
from backend.queue.queue_connection import get_rq_redis_connection

logger = logging.getLogger(__name__)

BATCH_PREFIX = "demo:batch:"
BATCH_TTL = 86400  # 24 hours
WEBHOOK_RETRIES = 3
WEBHOOK_BACKOFF_BASE = 1.0  # seconds

# Concurrency and Redis optimization (6.0: fast status for polling)
def _get_max_workers() -> int:
    """Max parallel workers; from DEMO_BATCH_MAX_WORKERS env (default 4)."""
    try:
        return max(1, min(32, int(os.environ.get("DEMO_BATCH_MAX_WORKERS", "4"))))
    except (TypeError, ValueError):
        return 4


STATUS_WRITE_EVERY_N = 1  # Write on every completion for fast poll updates
STATUS_WRITE_INTERVAL_SEC = 1.0  # Or every N seconds, whichever comes first


def _get_batch_key(batch_id: str) -> str:
    return f"{BATCH_PREFIX}{batch_id}"


def get_batch_data(batch_id: str) -> Optional[Dict[str, Any]]:
    """Load batch status/results from Redis. Returns None if not found."""
    redis_client = get_redis_client()
    if not redis_client:
        return None
    key = _get_batch_key(batch_id)
    raw = redis_client.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _update_batch_status(
    redis_client,
    batch_id: str,
    status: str,
    total: int,
    completed: int,
    failed: int,
    results: List[Dict[str, Any]],
) -> None:
    """Persist batch status to Redis."""
    key = _get_batch_key(batch_id)
    data = {
        "status": status,
        "total": total,
        "completed": completed,
        "failed": failed,
        "results": results,
    }
    redis_client.setex(key, BATCH_TTL, json.dumps(data))


def _deliver_webhook(
    callback_url: str,
    payload: Dict[str, Any],
) -> None:
    """
    POST webhook payload to callback_url. Retries up to 3 times with exponential backoff.
    Logs failures; does not raise (best-effort delivery).
    """
    for attempt in range(WEBHOOK_RETRIES):
        try:
            req = urllib.request.Request(
                callback_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    logger.info(f"Webhook delivered to {callback_url[:60]}... (attempt {attempt + 1})")
                    return
                logger.warning(
                    f"Webhook returned HTTP {resp.status} from {callback_url[:50]}... (attempt {attempt + 1})"
                )
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
            logger.warning(
                f"Webhook delivery attempt {attempt + 1}/{WEBHOOK_RETRIES} failed: {e}"
            )
        if attempt < WEBHOOK_RETRIES - 1:
            time.sleep(WEBHOOK_BACKOFF_BASE * (2 ** attempt))


def _process_single_url(
    index: int,
    url_str: str,
    quality_mode: str,
    cache_prefix: str,
    cache_disabled: bool,
    batch_id: str,
    total: int,
) -> tuple[int, Dict[str, Any]]:
    """
    Process one URL; runs in worker thread. Returns (index, result_dict).
    Each worker creates its own engine for thread safety.
    """
    from backend.services.quality_profiles import get_quality_profile

    profile = get_quality_profile(quality_mode, url_str)
    config = PreviewEngineConfig(
        is_demo=True,
        enable_brand_extraction=True,
        enable_ai_reasoning=profile.ai_reasoning,
        enable_composited_image=True,
        enable_cache=not cache_disabled,
        enable_multi_agent=profile.multi_agent,
        enable_ui_element_extraction=profile.ui_extraction,
        quality_threshold=profile.threshold,
        max_quality_iterations=profile.iterations,
        allow_soft_pass=profile.allow_soft_pass,
        enforce_target_quality=profile.enforce_target_quality,
        min_soft_pass_overall=profile.min_soft_pass_overall,
        min_soft_pass_visual=profile.min_soft_pass_visual,
        min_soft_pass_fidelity=profile.min_soft_pass_fidelity,
    )
    engine = PreviewEngine(config)
    try:
        logger.info(f"Batch {batch_id}: processing URL {index + 1}/{total}: {url_str[:60]}...")
        result = engine.generate(url_str, cache_key_prefix=cache_prefix)
        return (
            index,
            {
                "url": url_str,
                "preview_image_url": result.composited_preview_image_url,
                "screenshot_url": result.screenshot_url,
                "title": result.title,
                "error": None,
            },
        )
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Batch {batch_id}: URL failed {url_str[:50]}...: {error_msg}")
        return (
            index,
            {
                "url": url_str,
                "preview_image_url": None,
                "screenshot_url": None,
                "title": None,
                "error": error_msg[:500],
            },
        )


def generate_demo_batch_job(
    batch_id: str,
    urls: List[str],
    quality_mode: str = "balanced",
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Background job to generate previews for multiple URLs.

    Args:
        batch_id: Unique batch job identifier
        urls: List of URLs to process
        quality_mode: Quality profile (fast, balanced, ultra)
        callback_url: Optional webhook URL. POST on completion (P8).

    Returns:
        Final batch status dict
    """
    redis_client = get_redis_client()
    if not redis_client:
        raise RuntimeError("Redis unavailable for batch job storage")

    total = len(urls)
    completed = 0
    failed = 0
    results: List[Dict[str, Any]] = []

    _update_batch_status(redis_client, batch_id, "running", total, 0, 0, [])

    cache_disabled = is_demo_cache_disabled()
    cache_prefix = f"demo:preview:v3:{quality_mode}:"

    # Pre-allocate results list by index for parallel workers
    results_by_index: List[Optional[Dict[str, Any]]] = [None] * total
    completed_lock = threading.RLock()  # RLock: _maybe_write_status acquires same lock
    last_status_write = [time.monotonic()]

    def _maybe_write_status(c: int, f: int, res: List[Dict[str, Any]]) -> None:
        with completed_lock:
            write = (c + f) % STATUS_WRITE_EVERY_N == 0 or (
                time.monotonic() - last_status_write[0] >= STATUS_WRITE_INTERVAL_SEC
            )
            if write:
                _update_batch_status(
                    redis_client, batch_id, "running", total, c, f, res
                )
                last_status_write[0] = time.monotonic()

    workers = min(_get_max_workers(), total) if total > 0 else 1
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _process_single_url,
                i, url_str, quality_mode, cache_prefix, cache_disabled,
                batch_id, total,
            ): i
            for i, url_str in enumerate(urls)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                _, result_item = future.result()
            except Exception as e:
                logger.exception(f"Batch {batch_id}: worker failed for index {idx}")
                result_item = {
                    "url": urls[idx],
                    "preview_image_url": None,
                    "screenshot_url": None,
                    "title": None,
                    "error": str(e)[:500],
                }
            with completed_lock:
                results_by_index[idx] = result_item
                if result_item.get("error") is None:
                    completed += 1
                else:
                    failed += 1
                ordered = [results_by_index[i] for i in range(total) if results_by_index[i] is not None]
                _maybe_write_status(completed, failed, ordered)

    results = [
        results_by_index[i]
        if results_by_index[i] is not None
        else {"url": urls[i], "preview_image_url": None, "screenshot_url": None, "title": None, "error": "Skipped or timeout"}
        for i in range(total)
    ]

    final_status = "completed" if failed == 0 else "completed"  # Partial success still "completed"
    if completed == 0:
        final_status = "failed"

    _update_batch_status(
        redis_client, batch_id, final_status, total, completed, failed, results
    )

    logger.info(f"Batch {batch_id}: done. completed={completed}, failed={failed}")

    # P8: Webhook on completion — fire-and-forget (non-blocking)
    if callback_url:
        result_urls = [
            r.get("preview_image_url") or r.get("screenshot_url")
            for r in results
            if r.get("error") is None and (r.get("preview_image_url") or r.get("screenshot_url"))
        ]
        failed_urls = [r["url"] for r in results if r.get("error")]
        error_summary = f"{failed} of {total} URLs failed" if failed else None
        payload = {
            "job_id": batch_id,
            "status": final_status,
            "result_urls": result_urls,
            "failed_urls": failed_urls,
            "error_summary": error_summary,
        }

        def _run_webhook() -> None:
            _deliver_webhook(callback_url, payload)

        threading.Thread(target=_run_webhook, daemon=True).start()

    return {
        "job_id": batch_id,
        "status": final_status,
        "total": total,
        "completed": completed,
        "failed": failed,
        "results": results,
    }
