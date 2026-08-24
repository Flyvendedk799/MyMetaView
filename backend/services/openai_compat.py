"""LLM-gateway compatibility net — now a detector, not a workaround.

The gateway routes to a model that returns HTTP 400 for ``temperature`` and
``seed``. This module was the fix: patch the SDK once, drop those parameters
before every request, and stop dozens of call sites from failing.

It worked, and it hid the problem. A call site that passed ``temperature``
looked fine, because the patch quietly removed it — so nobody knew which code
depended on the patch, and "the orchestrator is broken" was the shape the
incident took rather than "one parameter needs a config change".

The real fix is now upstream: ``ModelSpec.supports_temperature`` declares what
each model accepts and the call sites simply do not send what it rejects
(``preview/reasoning/models.py``). Every preview call site has been converted.

What remains here is a net for the paths that have not — ``ai_provider``'s own
request model, and any future code — and it now **logs a warning naming the
caller** whenever it actually drops something. A silent workaround becomes a
signal that one more call site needs converting.
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
        dropped = [key for key in _DROP_PARAMS if key in kwargs]
        if dropped:
            # Name the caller: the point is that this should stop happening,
            # and it cannot stop happening if nobody knows where it happens.
            import traceback

            caller = "unknown"
            for frame in reversed(traceback.extract_stack()[:-1]):
                if "openai" not in frame.filename and "site-packages" not in frame.filename:
                    caller = f"{frame.filename.rsplit('/', 1)[-1]}:{frame.lineno}"
                    break
            logger.warning(
                "openai_compat dropped %s from a request made at %s — that call "
                "site should take its parameters from a ModelSpec instead",
                ", ".join(dropped), caller,
            )
            for key in dropped:
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
