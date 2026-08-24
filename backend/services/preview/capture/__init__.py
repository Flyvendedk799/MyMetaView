"""Capture: getting a screenshot and HTML out of a page that may not cooperate.

The stage that talks to the outside world, and therefore the stage that fails
most. Three things make it survivable:

  **Hedging.** Playwright and the screenshot API were a sequential fallback:
  wait the full local timeout, *then* start the remote one. Now the remote
  provider is fired when the local one has not answered within a few seconds
  and the first success wins, so a slow local capture costs seconds, not the
  whole budget.

  **A per-domain circuit breaker.** One hostile domain in a 200-URL bulk job
  used to burn its full capture timeout 200 times. After a few failures the
  breaker opens for that domain and the remaining URLs degrade immediately.

  **HTML-only as a real outcome.** A page that refuses a browser but serves
  markup still makes a genuine card from its metadata. That is a degradation
  worth recording, not a failure worth raising.
"""

from backend.services.preview.capture.stage import (
    capture_page,
    domain_breaker,
    hedged_screenshot,
)

__all__ = ["capture_page", "domain_breaker", "hedged_screenshot"]
