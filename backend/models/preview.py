"""SQLAlchemy ORM model for Preview."""
from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.db import Base


class Preview(Base):
    """SQLAlchemy ORM model for previews table."""
    __tablename__ = "previews"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    domain = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False, index=True)
    image_url = Column(String, nullable=False)
    highlight_image_url = Column(String, nullable=True)  # 16:9 cropped highlight region
    composited_image_url = Column(String, nullable=True)  # Designed UI card image (screenshot + typography overlay)
    description = Column(String, nullable=True)
    keywords = Column(String, nullable=True)  # Comma-separated string for now
    tone = Column(String, nullable=True)
    ai_reasoning = Column(String, nullable=True)
    # Which lane produced this card: "ai" (the art director designed it for this
    # page) or "template" (built from the page's own metadata, past the plan's
    # monthly AI allowance). Rows predating the split read as "ai", which is what
    # they were.
    generation_mode = Column(String, nullable=False, server_default="ai", default="ai")
    # The layout that actually rendered this card — one of premium_card_renderer's
    # LAYOUTS. Shown in the dashboard and used as the starting point when the
    # user re-rolls with a different layout.
    layout = Column(String, nullable=True)
    # Everything needed to re-render this card without re-capturing the page or
    # calling the model: composition spec, palette, brand name, proof, cta, and
    # R2 URLs for the two crops. Absent on previews generated before this existed
    # (and on any that fell through to the legacy renderer), which is why every
    # consumer treats "no spec" as "a re-render needs a full regeneration".
    render_spec = Column(JSON, nullable=True)
    # "Design this one from the page alone." Set when the preview is added, and
    # kept on the row so a re-roll or a bulk re-run honours the same choice
    # rather than quietly putting the site's branding back on the card.
    ignore_site_branding = Column(
        Boolean, nullable=False, server_default="0", default=False
    )
    # The same card composed at each platform's aspect — {"square": url, ...}.
    # Produced by a pure render off `render_spec`, so filling this in costs no
    # AI allowance and no page capture; absent until the fan-out has run.
    platform_images = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    monthly_clicks = Column(Integer, default=0, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)

    @property
    def can_rerender(self) -> bool:
        """Can this card be re-rendered without regenerating it?

        Only previews that went through the premium renderer carry a spec; ones
        from before it existed, or that fell through to the legacy generator,
        have to be regenerated from the page.
        """
        spec = self.render_spec
        return bool(isinstance(spec, dict) and spec.get("composition"))

    def image_for(self, size: str) -> str:
        """The card at one platform's aspect, falling back to the wide card.

        A caller asking for a square should get *something* shareable even
        before the fan-out has run, and the wide card is what every platform
        accepted before per-platform renders existed.
        """
        images = self.platform_images if isinstance(self.platform_images, dict) else {}
        return images.get(size) or self.composited_image_url or self.image_url

    # Relationships
    user = relationship("User", back_populates="previews")
    organization = relationship("Organization", back_populates="previews")
    analytics_events = relationship("AnalyticsEvent", back_populates="preview")
    analytics_aggregates = relationship("AnalyticsDailyAggregate", back_populates="preview")
    variants = relationship("PreviewVariant", back_populates="preview", cascade="all, delete-orphan")

