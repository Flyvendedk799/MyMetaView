"""Prepare all dependent images before changing a card's visible state."""
from copy import deepcopy
from fastapi import HTTPException
from sqlalchemy.orm.exc import StaleDataError
from backend.services.card_rerender import rerender_card


def render_revision(preview, spec, title, description):
    spec = deepcopy(spec)
    spec.update(title=title, subtitle=description or "")
    images = {}
    layout = None
    for size in dict.fromkeys(["wide", *(preview.platform_images or {})]):
        image, rendered_layout = rerender_card(spec, url=preview.url, title=title,
                                               subtitle=description, size=size)
        if not image:
            raise HTTPException(502, "Could not render every card size. Nothing was saved.")
        images[size] = image
        if size == "wide":
            layout = rendered_layout
    variants = []
    for variant in preview.variants:
        if variant.variant_key == "a":
            variants.append((variant, title, description, images["wide"]))
        else:
            image, _ = rerender_card(spec, url=preview.url, title=variant.title,
                                    subtitle=variant.subtitle or variant.description)
            if not image:
                raise HTTPException(502, "Could not render every variant. Nothing was saved.")
            variants.append((variant, variant.title, variant.description, image))
    spec["rendered_layout"] = layout
    return spec, images, variants


def apply_revision(preview, rendered):
    spec, images, variants = rendered
    preview.title = spec["title"]
    preview.description = spec["subtitle"]
    preview.render_spec = spec
    preview.layout = spec["rendered_layout"]
    preview.image_url = preview.composited_image_url = images["wide"]
    preview.platform_images = images
    for variant, title, description, image in variants:
        variant.title, variant.description, variant.image_url = title, description, image
        if variant.variant_key == "a":
            variant.subtitle = description


def commit_card(db):
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(409, "This card changed while rendering. Reload and try again.") from exc
