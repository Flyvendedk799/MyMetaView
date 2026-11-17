"""Describe observed traffic without inventing audience impressions."""
from alembic import op
import sqlalchemy as sa
revision='20261117_analytics_sources'
down_revision='20261117_bulk_runs'
branch_labels=depends_on=None

def upgrade():
    for name in ('event_source','campaign','variant'):
        op.add_column('analytics_events',sa.Column(name,sa.String(),nullable=True))

def downgrade():
    with op.batch_alter_table('analytics_events') as batch:
        for name in ('event_source','campaign','variant'):batch.drop_column(name)
