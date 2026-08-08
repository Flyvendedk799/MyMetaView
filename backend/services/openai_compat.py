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


# Our own marker. Do NOT use functools.wraps/__wrapped__ as the "already
# patched" signal — the OpenAI SDK's create() is decorated with @required_args,
# which already sets __wrapped__, so that check would falsely think it was
# patched and skip us (the original bug this shim first shipped with).
_MARKER = "_gateway_compat_patched"


def _wrap(original):
    def _patched(self, *args, **kwargs):
        for key in _DROP_PARAMS:
            if key in kwargs:
                kwargs.pop(key, None)
        return original(self, *args, **kwargs)
    _patched.__name__ = getattr(original, "__name__", "create")
    _patched.__doc__ = getattr(original, "__doc__", None)
    _patched.__wrapped__ = original
    setattr(_patched, _MARKER, True)
    return _patched


def _patch(cls) -> bool:
    """Wrap cls.create once. Returns True if the class now carries our wrapper."""
    create = cls.__dict__.get("create", getattr(cls, "create", None))
    if create is None:
        return False
    if getattr(create, _MARKER, False):
        return True  # already ours
    cls.create = _wrap(create)
    return True


def install_openai_gateway_compat() -> bool:
    """Patch OpenAI SDK chat.completions.create (sync + async) to drop params the
    gateway's model rejects. Idempotent; returns True if the patch is in place."""
    global _INSTALLED
    if _INSTALLED:
        return True
    patched_any = False
    try:
        from openai.resources.chat.completions import Completions
        patched_any = _patch(Completions) or patched_any
    except Exception as e:  # pragma: no cover
        logger.debug("openai_compat: sync patch skipped: %s", e)
    try:
        from openai.resources.chat.completions import AsyncCompletions
        patched_any = _patch(AsyncCompletions) or patched_any
    except Exception as e:  # pragma: no cover
        logger.debug("openai_compat: async patch skipped: %s", e)
    if patched_any:
        _INSTALLED = True
        logger.info("openai_compat installed: dropping %s from chat requests", ", ".join(_DROP_PARAMS))
    return _INSTALLED


# Self-install on import so merely importing this module is enough.
install_openai_gateway_compat()
