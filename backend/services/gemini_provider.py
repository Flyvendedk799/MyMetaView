"""Gemini / Antigravity Cloud Code provider.

Calls Google's internal Cloud Code endpoint using an Antigravity OAuth token,
the same way ``agy`` CLI does after a Google login. The endpoint format is
different from the public ``generativelanguage.googleapis.com`` API:

    POST https://daily-cloudcode-pa.googleapis.com/v1internal:generateContent

with the model id, a ``project`` field, and ``request.contents`` wrapping the
actual conversation. This module builds that request shape from standard
messages.

For metered API keys, it uses the public Google AI Studio endpoint instead.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Cloud Code endpoints (from ai-auth's clients/options.ts)
CLOUD_CODE_DAILY_BASE_URL = "https://daily-cloudcode-pa.googleapis.com/v1internal"
CLOUD_CODE_PROD_BASE_URL = "https://cloudcode-pa.googleapis.com/v1internal"
GOOGLE_ENTERPRISE_PROJECT = "aicode-consumers"


def normalize_model_id(model: str) -> str:
    """Strip ``models/`` prefix and apply known rewrites (from ai-auth)."""
    bare = model.removeprefix("models/").strip()
    if bare in ("gemini-3.1-pro", "gemini-3-pro"):
        return "gemini-3.1-pro-low"
    return bare


def _to_code_assist_request(
    model: str,
    messages: List[Dict[str, Any]],
    *,
    system_instruction: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a Cloud Code / Code Assist generateContent payload."""
    contents = []
    for msg in messages:
        role = "model" if msg.get("role") == "assistant" else msg.get("role", "user")
        text = msg.get("content", "")
        if isinstance(text, list):
            parts = []
            for part in text:
                if isinstance(part, dict) and "text" in part:
                    parts.append({"text": part["text"]})
                else:
                    parts.append({"text": str(part)})
        else:
            parts = [{"text": str(text)}]
        contents.append({"role": role, "parts": parts})

    wire_model = normalize_model_id(model)

    body: Dict[str, Any] = {
        "model": wire_model,
        "request": {"contents": contents},
    }

    if project_id and project_id != GOOGLE_ENTERPRISE_PROJECT:
        body["project"] = project_id

    if system_instruction:
        body["request"]["systemInstruction"] = {
            "role": "system",
            "parts": [{"text": system_instruction}],
        }

    return body


async def call_gemini_cloud_code(
    access_token: str,
    *,
    model: str = "gemini-2.5-flash",
    messages: List[Dict[str, Any]],
    system_prompt: Optional[str] = None,
    project_id: Optional[str] = None,
    max_tokens: int = 4096,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Make a generation call through the Cloud Code endpoint (subscription path).

    Uses the daily endpoint by default (matches real ``agy`` post-login behaviour
    for personal AI — the prod endpoint often false-429s for consumer tokens).
    """
    resolved_url = base_url or CLOUD_CODE_DAILY_BASE_URL
    url = f"{resolved_url}:generateContent"

    body = _to_code_assist_request(
        model,
        messages,
        system_instruction=system_prompt,
        project_id=project_id,
    )

    # Personal tokens must NOT send x-goog-user-project: aicode-consumers
    header_project = (
        project_id
        if project_id and project_id != GOOGLE_ENTERPRISE_PROJECT
        else None
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "antigravity/1.21.9 linux/amd64",
    }
    if header_project:
        headers["x-goog-user-project"] = header_project

    logger.info(
        "Gemini Cloud Code call: model=%s, url=%s",
        normalize_model_id(model), resolved_url,
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=body,
            headers=headers,
            timeout=120.0,
        )

    if response.status_code >= 400:
        error_text = response.text[:500]
        logger.error("Gemini Cloud Code error %d: %s", response.status_code, error_text)
        raise RuntimeError(
            f"Gemini Cloud Code returned HTTP {response.status_code}: {error_text}"
        )

    result = response.json()

    # Extract text from the Cloud Code response format
    candidates = result.get("candidates", [])
    if not candidates:
        return {"content": "", "model": model, "usage": {}}

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)

    usage = result.get("usageMetadata", {})

    return {
        "content": text,
        "model": model,
        "usage": {
            "input_tokens": usage.get("promptTokenCount", 0),
            "output_tokens": usage.get("candidatesTokenCount", 0),
        },
    }
