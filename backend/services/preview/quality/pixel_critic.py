"""A vision model looking at the finished card.

The mechanical metrics catch what can be measured: contrast ratios, ink at the
edge, an empty logo slot. They cannot tell you the headline is a truncated
sentence fragment, or that the card says something the page does not, or that
the composition is simply ugly. That needs eyes.

So this is deliberately narrow. One call, one short rubric, on the *rendered
PNG* — not on the dicts that produced it, which is what the previous critic
graded and why a card could score 0.9 while shipping unreadable. It runs at most
once per generation, on a small vision model, and only when the budget allows;
its verdict feeds the soft-pass decision rather than overriding it.

An unavailable or slow critic is a normal outcome. The mechanical score already
gates the hard failures, so a missing critic costs nuance, not safety.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.services.preview.observability.reason_codes import Degradation, Stage

logger = logging.getLogger(__name__)


RUBRIC = """You are looking at a link-preview card that will appear on Slack, X and LinkedIn.

Judge only what you can see in the image. Score three things 0-1:

  readability  Is the headline legible at a glance? Is any text clipped,
               overlapping, or running off the edge?
  balance      Is the composition deliberate — weight distributed, whitespace
               used — or does it look like elements landed at random?
  brand_match  Do the colors and type feel like they belong to the site named
               on the card, or like a generic template?

Then answer:
  verdict      "ship" | "fix" | "reject"
  issues       Up to three short, concrete problems. Empty if none.

"reject" means the card is unusable (unreadable text, blank canvas, broken
layout). "fix" means it is shippable but visibly weak. Be strict about
readability and forgiving about taste.

Return JSON only: {"readability":0-1,"balance":0-1,"brand_match":0-1,
"verdict":"...","issues":["..."]}"""


@dataclass
class CritiqueResult:
    """What the critic saw."""

    readability: float = 0.0
    balance: float = 0.0
    brand_match: float = 0.0
    verdict: str = "skipped"
    issues: List[str] = field(default_factory=list)
    ran: bool = False
    error: Optional[str] = None

    @property
    def overall(self) -> float:
        """Readability is weighted highest: it is the only one of the three
        that can make a card useless rather than merely weak."""
        return round(
            0.5 * self.readability + 0.25 * self.balance + 0.25 * self.brand_match, 4
        )

    @property
    def rejects(self) -> bool:
        return self.ran and self.verdict == "reject"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "readability": self.readability,
            "balance": self.balance,
            "brand_match": self.brand_match,
            "overall": self.overall,
            "verdict": self.verdict,
            "issues": list(self.issues),
            "ran": self.ran,
            "error": self.error,
        }


def critique_card(
    png: Optional[bytes],
    *,
    url: str = "",
    brand_name: Optional[str] = None,
    state: Optional[Any] = None,
) -> CritiqueResult:
    """Ask a vision model whether this card is shippable.

    Bounded by the render stage's remaining budget and skipped entirely when
    there is none: a critic that pushes a job past its deadline has cost more
    than its opinion is worth.
    """
    if not png:
        return CritiqueResult(error="no card to critique")

    if state is not None and state.budget.remaining() < 8.0:
        _record(state, Degradation.QUALITY_PIXEL_CRITIC_SKIPPED, "no budget left for the critic")
        return CritiqueResult(verdict="skipped", error="budget exhausted")

    try:
        from openai import OpenAI

        from backend.core.config import settings
        from backend.services.preview.reasoning.models import spec_for
        from backend.services.preview.reasoning.structured import parse_json_response, record_usage

        if not getattr(settings, "OPENAI_API_KEY", ""):
            _record(state, Degradation.QUALITY_PIXEL_CRITIC_SKIPPED, "no API key configured")
            return CritiqueResult(verdict="skipped", error="no api key")

        spec = spec_for("pixel_critic")
        client_kwargs: Dict[str, Any] = {
            "api_key": settings.OPENAI_API_KEY,
            "timeout": spec.timeout_s,
        }
        base_url = (getattr(settings, "OPENAI_BASE_URL", "") or "").strip()
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        context = f"The card is for {url}."
        if brand_name:
            context += f" The brand is {brand_name}."

        kwargs = dict(spec.request_kwargs())
        kwargs.update(
            messages=[
                {"role": "system", "content": "You are a demanding art director. Output JSON only."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{RUBRIC}\n\n{context}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64," + base64.b64encode(png).decode(),
                                "detail": "low",
                            },
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            timeout=spec.timeout_s,
        )
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 — a missing opinion is not a failure
        logger.info("Pixel critic unavailable: %s", exc)
        _record(state, Degradation.QUALITY_PIXEL_CRITIC_SKIPPED, str(exc)[:120])
        return CritiqueResult(error=str(exc)[:200])

    usage = getattr(response, "usage", None)
    if usage is not None and state is not None:
        try:
            from backend.services.preview.reasoning.models import record_usage as _usage

            _usage(
                state.trace, "pixel_critic", spec,
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            )
        except Exception:  # noqa: BLE001
            pass

    content = ""
    try:
        content = response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        pass

    from backend.services.preview.reasoning.structured import parse_json_response

    parsed = parse_json_response(content)
    if not parsed.valid:
        _record(state, Degradation.QUALITY_PIXEL_CRITIC_SKIPPED, "critic returned unparseable output")
        return CritiqueResult(error="unparseable critic output")

    data = parsed.data
    result = CritiqueResult(
        readability=_clamp(data.get("readability")),
        balance=_clamp(data.get("balance")),
        brand_match=_clamp(data.get("brand_match")),
        verdict=str(data.get("verdict") or "ship").lower(),
        issues=[str(i)[:120] for i in (data.get("issues") or [])][:3],
        ran=True,
    )

    code = (
        Degradation.QUALITY_PIXEL_CRITIC_FAIL
        if result.verdict in ("fix", "reject")
        else Degradation.QUALITY_PIXEL_CRITIC_PASS
    )
    _record(state, code, f"{result.verdict}: " + ("; ".join(result.issues) or f"overall {result.overall:.2f}"))
    return result


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _record(state: Optional[Any], code: Degradation, detail: str) -> None:
    if state is None:
        return
    try:
        state.trace.degrade(code, Stage.QUALITY, detail=detail[:200])
    except Exception:  # noqa: BLE001
        pass
