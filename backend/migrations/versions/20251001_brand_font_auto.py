"""Brand fonts: the stock "Inter" becomes "auto".

Every brand row was created with font_family="Inter" and the My Site picker
opened on it, so the value records nobody's choice. It was not drawable either:
Inter is neither embedded in the renderer's font CSS nor installed in the worker
image, so those cards fell back to IBM Plex Sans and lost the Bricolage display
face the demo draws with. "auto" is the card's own type.

Colours are normalised to lowercase #rrggbb on the way, so the stock-palette
check in preview/branding.py compares like with like.
"""
from alembic import op
import sqlalchemy as sa

revision = "20251001_brand_font_auto"
down_revision = "20250929_finish_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE brand_settings SET font_family = 'auto' "
        "WHERE font_family IS NULL OR lower(font_family) IN ('inter', '')"
    )
    for column in ("primary_color", "secondary_color", "accent_color"):
        op.execute(f"UPDATE brand_settings SET {column} = lower({column})")
    with op.batch_alter_table("brand_settings") as batch:
        batch.alter_column(
            "font_family",
            existing_type=sa.String(),
            existing_nullable=False,
            server_default="auto",
        )


def downgrade() -> None:
    with op.batch_alter_table("brand_settings") as batch:
        batch.alter_column(
            "font_family",
            existing_type=sa.String(),
            existing_nullable=False,
            server_default=None,
        )
    op.execute("UPDATE brand_settings SET font_family = 'Inter' WHERE font_family = 'auto'")
