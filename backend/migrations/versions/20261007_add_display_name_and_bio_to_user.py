"""Add display_name and bio to users

Revision ID: 20261007_user_profile
Revises: 20251001_brand_font_auto
Create Date: 2026-10-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261007_user_profile'
down_revision = '20251001_brand_font_auto'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('display_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('bio', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'bio')
    op.drop_column('users', 'display_name')
