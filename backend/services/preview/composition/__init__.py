"""Composition: turning a request into a renderable fact.

The art director names a layout and asks for a hero visual. Neither is a fact
until this stage checks it: the crop may have grabbed a nav bar, the logo may be
invisible on the panel it was assigned, the customer may have overridden the
layout entirely. Resolving all of that *before* the renderer sees it is what
makes ``CompositionSpec`` a pure input and re-rendering a pure function.

``build_minimal_spec`` is the other half. When reasoning fails, degradation
means a simpler spec through the same renderer — title, brand colors, wordmark —
never an older renderer. That is the single-render-path rule made concrete.
"""

from backend.services.preview.composition.builder import (
    build_minimal_spec,
    build_spec,
    resolve_visual,
)

__all__ = ["build_minimal_spec", "build_spec", "resolve_visual"]
