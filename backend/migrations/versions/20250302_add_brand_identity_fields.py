"""add brand identity + preview-card preference fields to brand_settings

Identity (name, tagline, description, audience, voice) is what the previews are
generated from, so it lives next to the colours on brand_settings.

The preview_* / force_brand_colors / hide_watermark columns shipped earlier
without a migration (they were created by metadata.create_all on fresh installs),
so they are added here too — guarded by an inspector check, which keeps this
migration a no-op on databases that already have them.

Revision ID: 20250302_add_brand_identity_fields
Revises: 20250301_create_published_sites_tables
Create Date: 2025-03-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250302_add_brand_identity_fields'
down_revision: Union[str, None] = '20250301_create_published_sites_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (column, type, server_default) — mirrors backend/models/brand.py. Columns with a
# server_default are NOT NULL (the default backfills existing rows); the free-text
# identity fields are nullable, where NULL means "infer it from the page".
NEW_COLUMNS = [
    ('brand_name', sa.String(), None),
    ('tagline', sa.String(), None),
    ('brand_description', sa.String(), None),
    ('audience', sa.String(), None),
    ('voice', sa.String(), 'auto'),
    ('preview_layout', sa.String(), 'auto'),
    ('preview_panel', sa.String(), 'auto'),
    ('preview_accent', sa.String(), 'auto'),
    ('force_brand_colors', sa.Boolean(), '0'),
    ('hide_watermark', sa.Boolean(), '0'),
]


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = {col['name'] for col in inspector.get_columns('brand_settings')}

    for name, coltype, default in NEW_COLUMNS:
        if name in existing:
            continue
        op.add_column(
            'brand_settings',
            sa.Column(name, coltype, nullable=default is None, server_default=default),
        )


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = {col['name'] for col in inspector.get_columns('brand_settings')}

    # Only the identity fields are this revision's own; the preview_* columns
    # predate it and are left in place.
    for name in ('brand_name', 'tagline', 'brand_description', 'audience', 'voice'):
        if name in existing:
            op.drop_column('brand_settings', name)
