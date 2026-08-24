"""store the per-platform renders of a card

``render_spec`` already holds everything needed to compose the same card at
another aspect, and doing so costs no page capture and no model call. This is
where the results go: ``{"square": url, "portrait": url}``, alongside the wide
card that ``composited_image_url`` already carries.

Nullable, because a preview that predates the fan-out genuinely has no
per-platform renders — and ``Preview.image_for`` falls back to the wide card,
which is what every platform accepted before this existed.

Revision ID: 20250307_add_platform_images_to_preview
Revises: 20250306_add_layout_render_spec_and_variant_angles
Create Date: 2025-03-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20250307_add_platform_images_to_preview'
down_revision: Union[str, None] = '20250306_add_layout_render_spec_and_variant_angles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: the startup schema sync may have added this already.
    from sqlalchemy import inspect

    inspector = inspect(op.get_bind())
    existing = {c['name'] for c in inspector.get_columns('previews')}
    if 'platform_images' not in existing:
        op.add_column('previews', sa.Column('platform_images', sa.JSON(), nullable=True))


def downgrade() -> None:
    from sqlalchemy import inspect

    inspector = inspect(op.get_bind())
    existing = {c['name'] for c in inspector.get_columns('previews')}
    if 'platform_images' in existing:
        op.drop_column('previews', 'platform_images')
