"""scope brand settings per domain

An organization can connect several domains and each is its own site, so brand
identity belongs to a domain rather than to the account. Adds a nullable
domain_id; the existing domain_id IS NULL row stays as the organization-wide
default and the fallback for domains that have not been customised.

No data migration: existing rows are already the organization default.

Revision ID: 20250304_add_domain_id_to_brand_settings
Revises: 20250302_add_snippet_install_tracking
Create Date: 2025-03-04 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250304_add_domain_id_to_brand_settings'
down_revision: Union[str, None] = '20250302_add_snippet_install_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: the startup schema sync may have added the column already.
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = {col['name'] for col in inspector.get_columns('brand_settings')}

    if 'domain_id' not in existing:
        op.add_column('brand_settings', sa.Column('domain_id', sa.Integer(), nullable=True))

    index_names = {ix['name'] for ix in inspector.get_indexes('brand_settings')}
    if 'ix_brand_settings_domain_id' not in index_names:
        op.create_index('ix_brand_settings_domain_id', 'brand_settings', ['domain_id'])


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    index_names = {ix['name'] for ix in inspector.get_indexes('brand_settings')}
    if 'ix_brand_settings_domain_id' in index_names:
        op.drop_index('ix_brand_settings_domain_id', table_name='brand_settings')

    existing = {col['name'] for col in inspector.get_columns('brand_settings')}
    if 'domain_id' in existing:
        op.drop_column('brand_settings', 'domain_id')
