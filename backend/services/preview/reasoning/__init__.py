"""Reasoning: the art director, the models it runs on, and its output contract.

The stage that reads a captured page and decides what the card says and how it
is composed. Three concerns, deliberately separate:

  ``models``      which model answers which purpose, and what it cost
  ``structured``  the output is a validated object, enforced in the request
  ``art_director``the stage itself — prompt in, ``ReasonedPreview`` out
"""

from backend.services.preview.reasoning.models import (
    MODEL_PRICES_PER_MTOK,
    ModelSpec,
    describe_map,
    record_usage,
    spec_for,
    stage_for,
)
from backend.services.preview.reasoning.structured import (
    ParsedOutput,
    StructuredOutputError,
    load_schema,
    parse_json_response,
    request_json,
    response_format_for,
    validate_against_schema,
)

__all__ = [
    "MODEL_PRICES_PER_MTOK",
    "ModelSpec",
    "ParsedOutput",
    "StructuredOutputError",
    "describe_map",
    "load_schema",
    "parse_json_response",
    "record_usage",
    "request_json",
    "response_format_for",
    "spec_for",
    "stage_for",
    "validate_against_schema",
]
