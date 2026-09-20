"""Anthropic provider for Claude subscription and API key credentials.

Uses the Anthropic Python SDK with the exact same options ai-auth's
``anthropicSubscriptionOptions`` / ``anthropicKeyOptions`` produce:

 * Subscription: ``authToken`` (not ``apiKey``), Claude Code beta flags,
   and the identity system block as the first message.
 * API key: standard ``api_key`` constructor.

The identity block is mandatory for Opus and Sonnet on subscription tokens.
See ai-auth's ``clients/identity.ts`` for the experiment that proved it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Claude Code identity block — must be the FIRST system block on subscription tokens.
# Exact match required; a different sentence or a merged block is refused with 429.
CLAUDE_CODE_SYSTEM = "You are Claude Code, Anthropic's official CLI for Claude."

# Beta flags and version a real Claude Code session sends.
CLAUDE_CODE_VERSION = "2.1.75"
CLAUDE_CODE_BETA = ",".join([
    "claude-code-20250219",
    "oauth-2025-04-20",
    "fine-grained-tool-streaming-2025-05-14",
    "interleaved-thinking-2025-05-14",
])


def create_anthropic_client(
    *,
    auth_token: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """Build an Anthropic client for either subscription or API key auth.

    Exactly one of ``auth_token`` (subscription) or ``api_key`` must be
    provided.  The SDK differences matter:

    * ``auth_token`` → sends ``Authorization: Bearer``, and ``api_key``
      must be ``None`` so the SDK does not also send ``x-api-key`` (which
      Anthropic validates when present, causing 401).
    * ``api_key`` → standard ``x-api-key`` header.
    """
    import anthropic

    if auth_token:
        return anthropic.Anthropic(
            auth_token=auth_token,
            api_key=None,  # Explicit null — see ai-auth trap #4
            default_headers={
                "anthropic-beta": CLAUDE_CODE_BETA,
                "user-agent": f"claude-cli/{CLAUDE_CODE_VERSION}",
                "x-app": "cli",
            },
        )
    elif api_key:
        return anthropic.Anthropic(api_key=api_key)
    else:
        raise ValueError("Either auth_token or api_key must be provided")


def call_anthropic(
    client,
    *,
    model: str,
    system_prompt: str,
    messages: List[Dict[str, Any]],
    max_tokens: int = 4096,
    temperature: float = 0.7,
    is_subscription: bool = False,
    response_format: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Make a completion call through the Anthropic API.

    When ``is_subscription`` is True, prepends the Claude Code identity
    block as the first system block (required for Opus/Sonnet on subscription
    tokens — without it Anthropic returns 429).
    """
    # Build system blocks
    if is_subscription:
        system = [
            {"type": "text", "text": CLAUDE_CODE_SYSTEM},
            {"type": "text", "text": system_prompt},
        ]
    else:
        system = system_prompt

    kwargs: Dict[str, Any] = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    # Only pass temperature for non-zero values (some models don't support it)
    if temperature > 0:
        kwargs["temperature"] = temperature

    logger.info(
        "Anthropic call: model=%s, is_sub=%s, max_tokens=%d",
        model, is_subscription, max_tokens,
    )

    response = client.messages.create(**kwargs)

    return {
        "content": response.content[0].text if response.content else "",
        "model": response.model,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "stop_reason": response.stop_reason,
    }
