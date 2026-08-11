"""record which lane generated each preview

Previews are now produced on one of two lanes: "ai", where the art director
reads the captured page and designs a card for it, or "template", where the
card is built from the page's own metadata once the account has spent its plan's
monthly AI allowance.

Existing rows are backfilled to "ai" — every preview generated before the split
went through the AI path, so that is not a guess.

Revision ID: 20250305_add_generation_mode_to_preview
Revises: 20250304_add_domain_id_to_brand_settings
Create Date: 2025-03-05 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250305_add_generation_mode_to_preview'
down_revision: Union[str, None] = '20250304_add_domain_id_to_brand_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: the startup schema sync may have added the column already.
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = {col['name'] for col in inspector.get_columns('previews')}

    if 'generation_mode' not in existing:
        op.add_column(
            'previews',
            sa.Column(
                'generation_mode',
                sa.String(),
                nullable=False,
                server_default='ai',
            ),
        )
    else:
        # Schema sync got here first. It adds a column as nullable when it cannot
        # prove a default is safe, so backfill any gaps before tightening.
        op.execute("UPDATE previews SET generation_mode = 'ai' WHERE generation_mode IS NULL")

        # SQLite cannot ALTER a column, and the tightening is not worth a
        # table rebuild there — local/dev databases are SQLite, production is
        # Postgres, and the backfill above already makes every row valid.
        if conn.dialect.name != 'sqlite':
            op.alter_column(
                'previews',
                'generation_mode',
                existing_type=sa.String(),
                nullable=False,
                server_default='ai',
            )


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing = {col['name'] for col in inspector.get_columns('previews')}

    if 'generation_mode' in existing:
        op.drop_column('previews', 'generation_mode')
