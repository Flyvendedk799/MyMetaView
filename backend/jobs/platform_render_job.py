"""Compose one card at every platform's aspect.

The stored ``render_spec`` holds everything a second render needs — composition,
palette, copy, proof, and the crops — so producing a square Instagram card or a
portrait Pinterest one is a pure rasterize. No page capture, no vision call, no
AI allowance spent.

Composing at each aspect matters more than it sounds. Cropping a 1200×630 card
down to a square throws away half the headline and puts the accent bar
somewhere arbitrary; composing *as* a square stacks the same elements at sizes
chosen for that shape. The renderer already supports this — the card is laid
out in HTML at whatever dimensions it is given — so the job is just the fan-out.

Runs on the bulk queue: it is never in a user's critical path, because the wide
card is already served and the others are an enhancement.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("preview_worker")


def render_platform_images_job(
    preview_id: int,
    sizes: Optional[List[str]] = None,
) -> Dict[str, object]:
    """Render one preview at every platform aspect and store the URLs.

    Idempotent by construction: it overwrites ``platform_images`` with what it
    produced this run, so a retry converges rather than accumulating.
    """
    from backend.db.session import SessionLocal
    from backend.models.preview import Preview as PreviewModel
    from backend.services.card_rerender import render_platform_sizes, spec_is_renderable

    db = SessionLocal()
    try:
        preview = db.query(PreviewModel).filter(PreviewModel.id == preview_id).first()
        if preview is None:
            return {"preview_id": preview_id, "status": "not_found"}

        if not spec_is_renderable(preview.render_spec):
            # Previews from before the spec existed have nothing to re-render
            # from. That is a real state, not an error — regenerating them is
            # the user's call because it costs an AI generation.
            logger.info("Preview %s has no render_spec; skipping platform renders", preview_id)
            return {"preview_id": preview_id, "status": "no_spec"}

        images = render_platform_sizes(
            preview.render_spec,
            url=preview.url,
            title=preview.title,
            subtitle=(preview.render_spec or {}).get("subtitle"),
            sizes=sizes,
            is_demo=False,
        )
        # The wide card already exists; storing it again under "wide" keeps the
        # map complete for a caller that just wants to iterate it.
        if preview.composited_image_url:
            images.setdefault("wide", preview.composited_image_url)

        preview.platform_images = images
        db.commit()

        logger.info("Rendered %d platform sizes for preview %s: %s",
                    len(images), preview_id, sorted(images))
        return {"preview_id": preview_id, "status": "ok", "sizes": sorted(images)}
    except Exception as exc:  # noqa: BLE001
        logger.error("Platform render failed for preview %s: %s", preview_id, exc, exc_info=True)
        db.rollback()
        return {"preview_id": preview_id, "status": "failed", "error": str(exc)}
    finally:
        db.close()


def enqueue_platform_renders(preview_id: int, sizes: Optional[List[str]] = None) -> bool:
    """Queue the fan-out. Never raises — the wide card is already served.

    On the bulk queue rather than the interactive one: nobody is waiting for
    these, and letting them compete with a user's own generation would trade a
    visible wait for an invisible enhancement.
    """
    try:
        from rq import Queue

        from backend.queue.queue_connection import get_rq_redis_connection

        Queue("bulk_generation", connection=get_rq_redis_connection()).enqueue(
            render_platform_images_job, preview_id, sizes, job_timeout=300,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.info("Could not queue platform renders for %s: %s", preview_id, exc)
        return False
