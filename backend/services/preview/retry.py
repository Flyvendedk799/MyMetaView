"""Retry policy and idempotency for preview jobs.

The DLQ recorded failures and stopped there. Everything that failed — a capture
timeout on a slow morning, a provider 5xx, a rate limit — needed a human to
notice and re-run it, and the ones nobody noticed simply never got a preview.

Two rules make that automatic without making it dangerous.

**Only transient reasons retry.** A job that failed because the URL is a 404, or
because the SSRF guard refused it, will fail identically on the next attempt;
retrying it burns a worker and delays real work. The reason-code taxonomy
already separates the two, so ``is_transient`` decides rather than a regex over
an exception string.

**Retries are idempotent.** A retried job that double-inserts variants leaves an
A/B test comparing a card against itself. An idempotency key derived from the
job's inputs — not from a timestamp — makes the second run recognise the first
one's work and take it over rather than duplicating it.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.services.preview.observability.reason_codes import FailureReason, is_transient

logger = logging.getLogger(__name__)

# Bounded, and deliberately small. A third attempt on a URL that failed twice
# for a transient reason is usually a URL that is not transiently broken.
MAX_AUTOMATIC_RETRIES = 2

# Exponential, with the first delay long enough that a rate limit has actually
# cleared by the time we ask again.
RETRY_DELAYS_S = (30, 180)

# How long an in-flight claim is honoured before another worker may take over.
# Longer than the total generation budget so a slow job is never stolen from.
CLAIM_TTL_S = 600


def idempotency_key(
    *,
    url: str,
    organization_id: Optional[int] = None,
    lane: str = "",
    attempt_of: Optional[str] = None,
) -> str:
    """Stable identity for one unit of preview work.

    Derived from what the job is *about*, never from when it started: a retry
    has to produce the same key as the attempt it is retrying, or it is not a
    retry, it is a duplicate.
    """
    if attempt_of:
        return attempt_of
    parts = [str(url or ""), str(organization_id or ""), str(lane or "")]
    return "pv-job-" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


@dataclass
class RetryDecision:
    """Should this failure be retried, and when?"""

    should_retry: bool
    delay_s: int = 0
    attempt: int = 0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_retry": self.should_retry,
            "delay_s": self.delay_s,
            "attempt": self.attempt,
            "reason": self.reason,
        }


def decide_retry(
    failure_reason: Optional[FailureReason | str],
    *,
    attempt: int = 0,
    max_retries: int = MAX_AUTOMATIC_RETRIES,
) -> RetryDecision:
    """Whether to re-enqueue a failed job.

    ``attempt`` is zero for the first failure. The decision is entirely a
    function of the reason code and the attempt count, which is what makes it
    testable without a queue.
    """
    if attempt >= max_retries:
        return RetryDecision(False, attempt=attempt,
                             reason=f"exhausted {max_retries} automatic retries")

    if not is_transient(failure_reason):
        code = failure_reason.value if isinstance(failure_reason, FailureReason) else failure_reason
        return RetryDecision(False, attempt=attempt,
                             reason=f"{code or 'unknown'} is not transient")

    delay = RETRY_DELAYS_S[min(attempt, len(RETRY_DELAYS_S) - 1)]
    code = failure_reason.value if isinstance(failure_reason, FailureReason) else failure_reason
    return RetryDecision(True, delay_s=delay, attempt=attempt + 1,
                         reason=f"{code} is transient; retrying in {delay}s")


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

_CLAIM_KEY = "pv:claim:{key}"


def claim(key: str, *, worker: str = "", ttl_s: int = CLAIM_TTL_S) -> bool:
    """Try to take exclusive ownership of a unit of work.

    ``SET NX`` with a TTL: the first worker wins, later ones see the claim and
    skip. The TTL is what keeps a crashed worker from holding a URL forever.
    Returns True when Redis is unavailable — refusing to work because we cannot
    coordinate would be worse than an occasional duplicate.
    """
    client = _redis()
    if client is None:
        return True
    try:
        return bool(client.set(_CLAIM_KEY.format(key=key),
                               worker or str(time.time()),
                               nx=True, ex=int(ttl_s)))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not claim %s: %s", key, exc)
        return True


def release(key: str) -> None:
    """Give up a claim early — on success, or on a failure we will not retry."""
    client = _redis()
    if client is None:
        return
    try:
        client.delete(_CLAIM_KEY.format(key=key))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not release claim %s: %s", key, exc)


def attempt_count(key: str) -> int:
    """How many times this unit of work has already been attempted."""
    client = _redis()
    if client is None:
        return 0
    try:
        value = client.get(f"pv:attempts:{key}")
        return int(value) if value else 0
    except Exception:  # noqa: BLE001
        return 0


def record_attempt(key: str, *, ttl_s: int = 24 * 3600) -> int:
    """Count an attempt and return the new total.

    Expiring after a day is deliberate: a URL that failed transiently yesterday
    should get a fresh budget today rather than inheriting a grudge.
    """
    client = _redis()
    if client is None:
        return 0
    try:
        pipe = client.pipeline()
        pipe.incr(f"pv:attempts:{key}")
        pipe.expire(f"pv:attempts:{key}", int(ttl_s))
        return int(pipe.execute()[0])
    except Exception:  # noqa: BLE001
        return 0


def clear_attempts(key: str) -> None:
    client = _redis()
    if client is None:
        return
    try:
        client.delete(f"pv:attempts:{key}")
    except Exception:  # noqa: BLE001
        pass


def _redis():
    try:
        from backend.services.preview_cache import get_redis_client

        return get_redis_client()
    except Exception:  # noqa: BLE001
        return None
