"""add snippet install tracking to domain

Records when a domain's embed snippet first reported in and when it was last
seen, so the dashboard can show a real install status instead of guessing.

Revision ID: 20250302_add_snippet_install_tracking
Revises: 20250301_create_published_sites_tables
Create Date: 2025-03-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250302_add_snippet_install_tracking'
down_revision: Union[str, None] = '20250301_create_published_sites_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_COLUMNS = (
    ('snippet_installed_at', sa.DateTime()),
    ('snippet_last_seen_at', sa.DateTime()),
    ('snippet_version', sa.String()),
)


def upgrade() -> None:
    # Idempotent: these may already exist on environments created from the model.
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = {col['name'] for col in inspector.get_columns('domains')}

    for name, column_type in NEW_COLUMNS:
        if name not in existing:
            op.add_column('domains', sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = {col['name'] for col in inspector.get_columns('domains')}

    for name, _column_type in reversed(NEW_COLUMNS):
        if name in existing:
            op.drop_column('domains', name)
