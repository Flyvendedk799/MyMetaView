"""Rendering: one rasterizer, no exceptions.

The engine used to carry five render stacks — the premium HTML renderer plus
four PIL compositors kept as fallbacks. Only the first ever shipped a card
anyone wanted; the others existed so a render failure would produce *something*,
and what they produced is the "gradient-only" regression class.

The rule is now: degradation means a simpler spec into the same renderer, never
an older renderer. A reasoning failure degrades to ``build_minimal_spec``, which
still renders through Chromium in MetaView's design language. If that fails
too, the honest outcome is a failed job, not a card that looks like a different
product.
"""

from backend.services.preview.rendering.renderer import (
    RenderError,
    render_card,
    render_spec_from,
    upload_card,
)

__all__ = ["RenderError", "render_card", "render_spec_from", "upload_card"]
