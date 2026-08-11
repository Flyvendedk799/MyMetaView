"""Preview database upsert job module."""
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.preview import Preview as PreviewModel


def determine_preview_type(url: str) -> str:
    """
    Determine preview type based on URL patterns.
    
    Args:
        url: URL to analyze
        
    Returns:
        Preview type: "product", "blog", or "landing"
    """
    url_lower = url.lower()
    if "/product" in url_lower or "/shop" in url_lower:
        return "product"
    elif "/blog" in url_lower or "/post" in url_lower:
        return "blog"
    else:
        return "landing"


def upsert_preview(
    db: Session,
    url: str,
    domain: str,
    title: str,
    description: Optional[str],
    image_url: str,
    preview_type: str,
    user_id: int,
    organization_id: int,
    keywords: Optional[str] = None,
    tone: Optional[str] = None,
    ai_reasoning: Optional[str] = None,
    highlight_image_url: Optional[str] = None,
    composited_image_url: Optional[str] = None,
    generation_mode: str = "ai",
    layout: Optional[str] = None,
    render_spec: Optional[dict] = None
) -> PreviewModel:
    """
    Upsert preview record in database.

    Args:
        db: Database session
        url: Preview URL
        domain: Domain name
        title: Preview title
        description: Preview description
        image_url: Image URL
        preview_type: Preview type
        user_id: User ID
        organization_id: Organization ID
        generation_mode: Lane that produced this card — "ai" or "template"
        layout: The card layout that actually rendered
        render_spec: Inputs for re-rendering this card without regenerating it

    Returns:
        Preview model instance
    """
    existing_preview = db.query(PreviewModel).filter(
        PreviewModel.url == url,
        PreviewModel.organization_id == organization_id
    ).first()
    
    if existing_preview:
        # Update existing preview
        existing_preview.title = title
        existing_preview.description = description
        existing_preview.image_url = image_url
        if highlight_image_url:
            existing_preview.highlight_image_url = highlight_image_url
        if composited_image_url:
            existing_preview.composited_image_url = composited_image_url
        existing_preview.keywords = keywords
        existing_preview.tone = tone
        existing_preview.ai_reasoning = ai_reasoning
        existing_preview.generation_mode = generation_mode
        # Only overwrite when this run produced one. A regeneration that fell
        # through to the legacy renderer has no spec, and clearing the old one
        # would strip re-render support from a preview that still has a card.
        if layout:
            existing_preview.layout = layout
        if render_spec:
            existing_preview.render_spec = render_spec
        if not existing_preview.type:
            existing_preview.type = preview_type
        
        db.commit()
        db.refresh(existing_preview)
        return existing_preview
    else:
        # Create new preview
        new_preview = PreviewModel(
            url=url,
            domain=domain,
            title=title,
            description=description,
            type=preview_type,
            image_url=image_url,
            highlight_image_url=highlight_image_url,
            composited_image_url=composited_image_url,
            keywords=keywords,
            tone=tone,
            ai_reasoning=ai_reasoning,
            generation_mode=generation_mode,
            layout=layout,
            render_spec=render_spec,
            user_id=user_id,
            organization_id=organization_id,
            created_at=datetime.utcnow(),
            monthly_clicks=0,
        )
        db.add(new_preview)
        db.commit()
        db.refresh(new_preview)
        return new_preview

