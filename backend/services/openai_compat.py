"""LLM-gateway compatibility shim.

The chat calls across this codebase go through the SubGate gateway, which routes
to an Anthropic model that returns HTTP 400 for parameters it considers
unsupported/deprecated — notably ``temperature`` ("deprecated for this model")
and ``seed``. Dozens of call sites (the multi-agent orchestrator, UI-element
extractor, design/brand extractors, reasoning stages, …) still pass these, so
they fail and fall back to weaker output.

Rather than edit every call site, we patch the OpenAI SDK once to drop these
params before the request is sent. This is a no-op for providers that DO accept
them (we simply omit and let the model default), and it is safe/idempotent.

Install is triggered on import (see bottom) and also exposed as
``install_openai_gateway_compat()`` for explicit calls from entry points.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Params the gateway's model rejects. Keep this list tight — only strip what is
# known to 400, so we don't silently swallow meaningful request options.
_DROP_PARAMS = ("temperature", "seed")

_INSTALLED = False


def _wrap(original):
    def _patched(self, *args, **kwargs):
        for key in _DROP_PARAMS:
            if key in kwargs:
                kwargs.pop(key, None)
        return original(self, *args, **kwargs)
    _patched.__name__ = getattr(original, "__name__", "create")
    _patched.__doc__ = getattr(original, "__doc__", None)
    _patched.__wrapped__ = original
    return _patched


def install_openai_gateway_compat() -> bool:
    """Patch OpenAI SDK chat.completions.create (sync + async) to drop params the
    gateway's model rejects. Idempotent; returns True if the patch is in place."""
    global _INSTALLED
    if _INSTALLED:
        return True
    patched_any = False
    # Sync client
    try:
        from openai.resources.chat.completions import Completions
        if not getattr(Completions.create, "__wrapped__", None):
            Completions.create = _wrap(Completions.create)
        patched_any = True
    except Exception as e:  # pragma: no cover
        logger.debug("openai_compat: sync patch skipped: %s", e)
    # Async client
    try:
        from openai.resources.chat.completions import AsyncCompletions
        if not getattr(AsyncCompletions.create, "__wrapped__", None):
            AsyncCompletions.create = _wrap(AsyncCompletions.create)
        patched_any = True
    except Exception as e:  # pragma: no cover
        logger.debug("openai_compat: async patch skipped: %s", e)
    if patched_any:
        _INSTALLED = True
        logger.info("openai_compat installed: dropping %s from chat requests", ", ".join(_DROP_PARAMS))
    return _INSTALLED


# Self-install on import so merely importing this module is enough.
install_openai_gateway_compat()
