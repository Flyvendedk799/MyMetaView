"""remember a preview that opted out of the site's branding

The My Site tab's brand reaches every card generated for that domain. One page
sometimes should not carry it — a guest post, a co-branded landing page, a
microsite — so the create dialog offers "disregard my site branding" and this
column is where that choice lives. It has to be on the row rather than only on
the request: a re-roll, a bulk re-run or a platform re-render all regenerate the
card later, and any of them silently re-branding the page would be the bug.

Defaults to false, which is what every existing preview did.

Revision ID: 20250308_add_ignore_site_branding_to_preview
Revises: 20250307_add_platform_images_to_preview
Create Date: 2025-03-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20250308_add_ignore_site_branding_to_preview'
down_revision: Union[str, None] = '20250307_add_platform_images_to_preview'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: the startup schema sync may have added this already.
    from sqlalchemy import inspect

    inspector = inspect(op.get_bind())
    existing = {c['name'] for c in inspector.get_columns('previews')}
    if 'ignore_site_branding' not in existing:
        op.add_column(
            'previews',
            sa.Column(
                'ignore_site_branding',
                sa.Boolean(),
                nullable=False,
                server_default='0',
            ),
        )


def downgrade() -> None:
    from sqlalchemy import inspect

    inspector = inspect(op.get_bind())
    existing = {c['name'] for c in inspector.get_columns('previews')}
    if 'ignore_site_branding' in existing:
        op.drop_column('previews', 'ignore_site_branding')
