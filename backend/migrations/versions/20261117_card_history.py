"""Draft and published snapshots, with immutable history."""
from alembic import op
import sqlalchemy as sa
revision = '20261117_card_history'
down_revision = '20261117_card_revision'
branch_labels = depends_on = None

def upgrade():
    op.add_column('previews', sa.Column('auto_publish', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('previews', sa.Column('published_snapshot', sa.JSON(), nullable=True))
    op.create_table('card_history', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('preview_id', sa.Integer(), sa.ForeignKey('previews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('preview_id','revision',name='uq_card_history_revision'))
    op.create_index('ix_card_history_preview_id', 'card_history', ['preview_id'])

def downgrade():
    op.drop_table('card_history')
    with op.batch_alter_table('previews') as batch:
        batch.drop_column('published_snapshot'); batch.drop_column('auto_publish')
