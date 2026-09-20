"""Alembic migration: Add ai_credentials table for encrypted AI credential storage."""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20250920_add_ai_credentials'
down_revision = None  # Will be auto-linked by Alembic
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_credentials',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('credential_key', sa.String(), nullable=False, index=True),
        sa.Column('encrypted_payload', sa.Text(), nullable=False),
        sa.Column('meta_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('organization_id', 'user_id', 'credential_key', name='uq_ai_credential_scope_key'),
    )


def downgrade() -> None:
    op.drop_table('ai_credentials')
