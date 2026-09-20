"""Credential-aware AI client for org/user AI credential resolution.

This module is the integration point between the preview generation pipeline
and the ai-auth credential stores. When a preview job runs, it calls
``resolve_ai_client`` with the organization id to get either:

  * An Anthropic client using the org's Claude subscription or API key, or
  * A Gemini Cloud Code caller using the org's Antigravity subscription, or
  * The platform's default OpenAI client (the existing ``reasoning_client``).

The resolution order matches the plan: user credentials → org credentials →
platform default.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def resolve_ai_credentials(
    org_id: Optional[int] = None,
    user_id: Optional[int] = None,
    db=None,
) -> Tuple[str, Dict[str, Any]]:
    """Resolve which AI provider and credentials to use.

    Returns:
        (provider, config) where provider is 'openai', 'anthropic', or 'gemini'
        and config contains the credentials needed for that provider.

    This runs the async credential stores in a sync context using
    ``asyncio.run()`` (safe in RQ worker processes which don't have a running
    event loop).
    """
    if not db:
        return ("openai", {})

    from backend.core.config import settings
    from backend.services.ai_auth.credential_store import SqlAlchemyCredentialStore
    from backend.services.ai_auth.claude_account_store import ClaudeAccountStore
    from backend.services.ai_auth.antigravity_account_store import AntigravityAccountStore
    from backend.services.ai_auth.api_key_store import ApiKeyStore

    secret = settings.SECRET_KEY

    async def _resolve():
        # 1. Check user-level Claude subscription
        if user_id:
            user_store = SqlAlchemyCredentialStore(db, user_id=user_id)
            claude = ClaudeAccountStore(user_store, secret)
            status = await claude.status(str(user_id))
            if status.connected:
                try:
                    token = await claude.token(str(user_id))
                    return ("anthropic", {"auth_token": token, "is_subscription": True})
                except Exception:
                    logger.warning("User %d Claude token refresh failed", user_id)

        # 2. Check org-level Claude subscription
        if org_id:
            org_store = SqlAlchemyCredentialStore(db, organization_id=org_id)
            claude = ClaudeAccountStore(org_store, secret)
            status = await claude.status(str(org_id))
            if status.connected:
                try:
                    token = await claude.token(str(org_id))
                    return ("anthropic", {"auth_token": token, "is_subscription": True})
                except Exception:
                    logger.warning("Org %d Claude token refresh failed", org_id)

        # 3. Check user-level Antigravity subscription
        if user_id:
            user_store = SqlAlchemyCredentialStore(db, user_id=user_id)
            agy = AntigravityAccountStore(user_store, secret)
            status = await agy.status(str(user_id))
            if status.connected:
                try:
                    token = await agy.token(str(user_id))
                    return ("gemini", {
                        "auth_token": token,
                        "project_id": status.project_id,
                    })
                except Exception:
                    logger.warning("User %d Antigravity token refresh failed", user_id)

        # 4. Check org-level Antigravity subscription
        if org_id:
            org_store = SqlAlchemyCredentialStore(db, organization_id=org_id)
            agy = AntigravityAccountStore(org_store, secret)
            status = await agy.status(str(org_id))
            if status.connected:
                try:
                    token = await agy.token(str(org_id))
                    return ("gemini", {
                        "auth_token": token,
                        "project_id": status.project_id,
                    })
                except Exception:
                    logger.warning("Org %d Antigravity token refresh failed", org_id)

        # 5. Check user-level API keys
        if user_id:
            user_store = SqlAlchemyCredentialStore(db, user_id=user_id)
            keys = ApiKeyStore(user_store, secret)
            for wire in ("anthropic", "openai"):
                resolved = await keys.resolve(wire)
                if resolved.ready and resolved.key:
                    return (wire, {"api_key": resolved.key})

        # 6. Check org-level API keys
        if org_id:
            org_store = SqlAlchemyCredentialStore(db, organization_id=org_id)
            keys = ApiKeyStore(org_store, secret)
            for wire in ("anthropic", "openai"):
                resolved = await keys.resolve(wire)
                if resolved.ready and resolved.key:
                    return (wire, {"api_key": resolved.key})

        # 7. Fall back to platform default
        return ("openai", {})

    try:
        # In RQ workers there's no running event loop
        return asyncio.run(_resolve())
    except RuntimeError:
        # If there IS a running loop (e.g. in tests), use it
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_resolve())
