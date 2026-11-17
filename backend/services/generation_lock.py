"""Serialize work for one organization/URL across generation entry points."""
from contextlib import contextmanager
from hashlib import sha256
from redis.exceptions import RedisError
from backend.core.config import ENV


@contextmanager
def generation_lock(organization_id, url):
    from backend.services.preview_cache import get_redis_client
    client = get_redis_client()
    lock = None
    if client is None and ENV == 'production':
        raise RuntimeError('Generation coordination is unavailable. Retry shortly.')
    if client is not None:
        candidate = client.lock(
            'generation:' + sha256(f'{organization_id}:{url}'.encode()).hexdigest(),
            timeout=660,
        )
        try:
            acquired = candidate.acquire(blocking=False)
        except RedisError as exc:
            if ENV == 'production':
                raise RuntimeError('Generation coordination is unavailable. Retry shortly.') from exc
        else:
            if not acquired:
                raise RuntimeError('This page is already generating. Retry after the current run finishes.')
            lock = candidate
    try:
        yield
    finally:
        if lock is not None:
            try:
                lock.release()
            except RedisError:
                pass  # Expired leases must not release a newer owner's lock.
