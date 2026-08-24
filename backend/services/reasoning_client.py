"""One model client and one breaker for the reasoning stages.

Two duplications lived here before. Every stage built its own ``OpenAI(...)``,
so the gateway base URL had to be right in four places; and there were two
circuit breakers — the registry in ``circuit_breaker.py`` and a hand-rolled
singleton in ``graceful_degradation`` — which meant model failures tripped one
of them and capture failures the other, and neither had the whole picture.

Both collapse here. ``get_client`` returns a pooled client pointed at whatever
endpoint is configured; ``reasoning_breaker`` returns the shared breaker other
AI paths already report to.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_clients: Dict[int, Any] = {}
_lock = threading.Lock()


def get_client(*, timeout: int = 60):
    """A model client for the configured endpoint.

    Cached per timeout, because the SDK's client is thread-safe and building one
    per call was pure overhead. ``OPENAI_BASE_URL`` points it at a gateway; unset
    means the vendor default, so existing deployments are unchanged.
    """
    with _lock:
        cached = _clients.get(timeout)
        if cached is not None:
            return cached

        from openai import OpenAI

        from backend.core.config import settings

        kwargs: Dict[str, Any] = {
            "api_key": settings.OPENAI_API_KEY,
            "timeout": timeout,
        }
        base_url = (getattr(settings, "OPENAI_BASE_URL", "") or "").strip()
        if base_url:
            kwargs["base_url"] = base_url

        client = OpenAI(**kwargs)
        _clients[timeout] = client
        return client


def reset_clients() -> None:
    """Drop cached clients. Tests use this after changing settings."""
    with _lock:
        _clients.clear()


def reasoning_breaker():
    """The shared breaker for model calls.

    One breaker for all reasoning means three consecutive provider failures stop
    us spending on a fourth, regardless of which stage hit them — which is the
    behaviour two separate breakers could not produce.
    """
    from backend.services.circuit_breaker import CircuitBreakerConfig, get_circuit_breaker

    return get_circuit_breaker(
        "ai_reasoning",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=120.0,
            success_threshold=1,
        ),
    )
