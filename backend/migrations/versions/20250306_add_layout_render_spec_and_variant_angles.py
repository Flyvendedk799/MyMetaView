"""record how a card was composed, and give variants their own identity

Two related additions:

``previews.layout`` / ``previews.render_spec`` capture how a card was actually
built — which layout survived asset resolution, plus the composition spec,
palette, copy and crop URLs behind it. With those stored, re-rendering a card at
a new size or with a different layout is a pure render: no page capture, no
vision call.

``preview_variants.angle`` / ``preview_variants.subtitle`` let a variant be a
genuinely different pitch rather than a truncation of the main one. Existing
rows keep their titles; they simply have no angle recorded, because the code
that produced them did not have one.

Revision ID: 20250306_add_layout_render_spec_and_variant_angles
Revises: 20250305_add_generation_mode_to_preview
Create Date: 2025-03-06 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250306_add_layout_render_spec_and_variant_angles'
down_revision: Union[str, None] = '20250305_add_generation_mode_to_preview'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All nullable: an older preview genuinely has no recorded layout or spec, and
# "unknown" is the honest representation of that.
_NEW_COLUMNS = {
    'previews': [
        ('layout', lambda: sa.Column('layout', sa.String(), nullable=True)),
        ('render_spec', lambda: sa.Column('render_spec', sa.JSON(), nullable=True)),
    ],
    'preview_variants': [
        ('angle', lambda: sa.Column('angle', sa.String(), nullable=True)),
        ('subtitle', lambda: sa.Column('subtitle', sa.String(), nullable=True)),
    ],
}


def upgrade() -> None:
    # Idempotent: the startup schema sync may have added these already.
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())

    for table, columns in _NEW_COLUMNS.items():
        existing = {c['name'] for c in inspector.get_columns(table)}
        for name, make_column in columns:
            if name not in existing:
                op.add_column(table, make_column())


def downgrade() -> None:
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())

    for table, columns in _NEW_COLUMNS.items():
        existing = {c['name'] for c in inspector.get_columns(table)}
        for name, _ in columns:
            if name in existing:
                op.drop_column(table, name)
