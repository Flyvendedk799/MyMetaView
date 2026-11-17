"""Durable runs and independently resumable work items."""
from alembic import op
import sqlalchemy as sa
revision='20261117_bulk_runs'
down_revision='20261117_site_coverage'
branch_labels=depends_on=None

def upgrade():
    op.create_table('bulk_runs',sa.Column('id',sa.String(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('domain',sa.String(),nullable=False),
        sa.Column('status',sa.String(),nullable=False),sa.Column('force',sa.Boolean(),nullable=False),
        sa.Column('ignore_branding',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_bulk_runs_organization_id','bulk_runs',['organization_id'])
    op.create_table('bulk_run_items',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('run_id',sa.String(),sa.ForeignKey('bulk_runs.id'),nullable=False),sa.Column('url',sa.String(),nullable=False),
        sa.Column('status',sa.String(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('lease',sa.String()),
        sa.Column('updated_at',sa.DateTime(),nullable=False),sa.Column('preview_id',sa.Integer(),sa.ForeignKey('previews.id',ondelete='SET NULL')),
        sa.Column('error',sa.String()),sa.UniqueConstraint('run_id','url',name='uq_bulk_run_url'))
    op.create_index('ix_bulk_run_items_run_id','bulk_run_items',['run_id'])

def downgrade():
    op.drop_table('bulk_run_items');op.drop_table('bulk_runs')
