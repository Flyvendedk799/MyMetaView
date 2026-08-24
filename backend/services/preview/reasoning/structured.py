"""Structured model output, enforced at the provider layer.

Every call site that wanted JSON had its own recovery ladder: strip a
```json fence, try ``json.loads``, regex out the first ``{...}``, try again,
retry the whole call with a simplified prompt, fall back to a hand-written
stub. Three copies of that ladder existed, each subtly different, and the stub
at the bottom is where "every page came out looking like the same template"
started.

The right place for the constraint is the request. ``request_json`` asks the
provider for schema-constrained output — ``json_schema`` where the model
supports it, ``json_object`` where it only supports that, plain text as the
last resort — and validates what comes back against the same schema. Recovery
still exists, because models are models, but it lives in one function and every
step it takes is reported so the trace can say the output was repaired.

Schemas come from ``backend/prompts/schemas/``: the files were already there,
they simply were not enforced.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "prompts" / "schemas"

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class StructuredOutputError(ValueError):
    """The model did not return usable structured output."""


@lru_cache(maxsize=16)
def load_schema(name: str) -> Optional[Dict[str, Any]]:
    """Load a JSON schema by filename stem, or None when it is not there."""
    path = _SCHEMA_DIR / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Schema %s unavailable: %s", name, exc)
        return None


@dataclass
class ParsedOutput:
    """What came back, and what we had to do to get it.

    ``repairs`` is the interesting field: an empty list means the model obeyed
    the schema, a non-empty one means it did not and we salvaged the response.
    The engine records the difference, so "the prompt has drifted" is visible
    in the trace before it is visible in the cards.
    """

    data: Dict[str, Any]
    repairs: List[str] = field(default_factory=list)
    valid: bool = True
    errors: List[str] = field(default_factory=list)

    @property
    def was_repaired(self) -> bool:
        return bool(self.repairs)


def parse_json_response(content: Optional[str]) -> ParsedOutput:
    """Text → dict, recording every recovery step it took.

    The ladder is unchanged in substance — fenced block, direct parse, first
    balanced object — but it exists exactly once, and each rung it descends is
    named in ``repairs`` instead of being invisible.
    """
    if not content or not str(content).strip():
        return ParsedOutput({}, valid=False, errors=["empty response"])

    text = str(content).strip()

    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return ParsedOutput(data)
        return ParsedOutput(
            {}, valid=False,
            errors=[f"expected object, got {type(data).__name__}"],
        )
    except json.JSONDecodeError:
        pass

    match = _OBJECT.search(text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return ParsedOutput(data, repairs=["extracted embedded object"])
        except json.JSONDecodeError:
            repaired = _close_truncated_object(match.group(0))
            if repaired is not None:
                return ParsedOutput(repaired, repairs=["closed truncated object"])

    # No closing brace at all — the model hit the token cap mid-object. Taking
    # everything from the first ``{`` and closing it recovers the fields it did
    # finish, which is strictly better than the hand-written stub that used to
    # sit at the bottom of this ladder and made every page render the same card.
    start = text.find("{")
    if start >= 0:
        repaired = _close_truncated_object(text[start:])
        if repaired is not None:
            return ParsedOutput(repaired, repairs=["closed truncated object"])

    return ParsedOutput({}, valid=False, errors=["no parseable JSON object"])


def _close_truncated_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort close of an object the model stopped writing mid-way."""
    trimmed = text.rstrip().rstrip(",")
    for _ in range(6):
        opens = trimmed.count("{") - trimmed.count("}")
        brackets = trimmed.count("[") - trimmed.count("]")
        if opens <= 0 and brackets <= 0:
            break
        candidate = trimmed + ("]" * max(0, brackets)) + ("}" * max(0, opens))
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            # Drop the trailing fragment — usually a half-written key — and retry.
            cut = max(trimmed.rfind(","), trimmed.rfind("{"), trimmed.rfind("["))
            if cut <= 0:
                return None
            trimmed = trimmed[:cut]
    return None


def validate_against_schema(
    data: Dict[str, Any],
    schema: Optional[Dict[str, Any]],
) -> List[str]:
    """Check required keys and declared types. Returns a list of problems.

    Deliberately not a full JSON Schema implementation — ``jsonschema`` would be
    a dependency for one rule we care about. Required-and-typed catches the
    failures that actually reach us: a missing ``title``, a ``tags`` that came
    back as a string, a confidence that arrived as prose.
    """
    if not schema or not isinstance(data, dict):
        return []

    problems: List[str] = []
    for key in schema.get("required", []) or []:
        if key not in data or data[key] is None:
            problems.append(f"missing required field: {key}")

    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for key, spec in (schema.get("properties") or {}).items():
        if key not in data or data[key] is None:
            continue
        declared = spec.get("type")
        expected = type_map.get(declared) if isinstance(declared, str) else None
        if expected and not isinstance(data[key], expected):
            problems.append(
                f"{key}: expected {declared}, got {type(data[key]).__name__}"
            )
    return problems


def response_format_for(
    schema_name: Optional[str],
    *,
    supports_json_schema: bool = True,
) -> Optional[Dict[str, Any]]:
    """The ``response_format`` to send so the model is constrained up front.

    Constraining the request is the actual fix; the parsing ladder is only the
    safety net. A provider that supports ``json_schema`` cannot return a
    non-conforming object at all, which is why we prefer it and only fall back
    to ``json_object`` where it is unavailable.
    """
    if not schema_name:
        return {"type": "json_object"}

    schema = load_schema(schema_name)
    if not schema or not supports_json_schema:
        return {"type": "json_object"}

    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "schema": _strip_unsupported(schema),
            "strict": False,
        },
    }


def _strip_unsupported(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Drop annotation keys providers reject in a response_format schema."""
    return {
        key: value
        for key, value in schema.items()
        if key not in ("$schema", "title", "description", "examples")
    }


def request_json(
    client: Any,
    *,
    messages: List[Dict[str, Any]],
    spec: Any,
    schema_name: Optional[str] = None,
    purpose: str = "art_director",
    trace: Optional[Any] = None,
) -> ParsedOutput:
    """One model call that is required to come back as a valid object.

    Takes the ``ModelSpec`` rather than a model string, so the parameters the
    gateway rejects are simply never sent — the reason ``openai_compat``'s
    SDK-wide monkey-patch existed. Records usage against the trace, so cost per
    stage is a by-product of making the call rather than a separate concern.
    """
    from backend.services.preview.reasoning.models import record_usage

    kwargs: Dict[str, Any] = dict(spec.request_kwargs())
    kwargs["messages"] = messages
    kwargs["timeout"] = getattr(spec, "timeout_s", 60)

    response_format = response_format_for(
        schema_name,
        supports_json_schema=getattr(spec, "supports_json_schema", True),
    )
    if response_format:
        kwargs["response_format"] = response_format

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        message = str(exc)
        # A gateway that rejects the strict schema format still answers a plain
        # json_object request. Retrying once without the schema beats failing
        # the stage over a capability we only wanted as an optimisation.
        if response_format and response_format.get("type") == "json_schema" and (
            "response_format" in message or "json_schema" in message
        ):
            logger.info("Provider rejected json_schema for %s; retrying as json_object", purpose)
            kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
        else:
            raise

    usage = getattr(response, "usage", None)
    if usage is not None:
        record_usage(
            trace, purpose, spec,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )

    content = ""
    try:
        content = response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        pass

    parsed = parse_json_response(content)
    if parsed.valid and schema_name:
        problems = validate_against_schema(parsed.data, load_schema(schema_name))
        if problems:
            parsed.errors.extend(problems)
            parsed.repairs.append("schema validation reported problems")
    return parsed
