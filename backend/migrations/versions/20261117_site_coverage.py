"""Recurring coverage policy and URL inventory."""
from alembic import op
import sqlalchemy as sa
revision='20261117_site_coverage'
down_revision='20261117_card_history'
branch_labels=depends_on=None

def upgrade():
    op.create_table('site_refresh_policies',sa.Column('domain_id',sa.Integer(),sa.ForeignKey('domains.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('enabled',sa.Boolean(),nullable=False),sa.Column('interval_hours',sa.Integer(),nullable=False),
        sa.Column('next_scan_at',sa.DateTime(),nullable=False),sa.Column('last_scan_at',sa.DateTime()),sa.Column('last_error',sa.String()))
    op.create_table('site_page_coverage',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('domain_id',sa.Integer(),sa.ForeignKey('domains.id',ondelete='CASCADE'),nullable=False),
        sa.Column('url',sa.String(),nullable=False),sa.Column('canonical_url',sa.String()),sa.Column('fingerprint',sa.String()),
        sa.Column('generated_fingerprint',sa.String()),sa.Column('sitemap_lastmod',sa.String()),sa.Column('state',sa.String(),nullable=False),
        sa.Column('error',sa.String()),sa.Column('checked_at',sa.DateTime()),sa.Column('generated_at',sa.DateTime()),
        sa.UniqueConstraint('domain_id','url',name='uq_coverage_url'))
    op.create_index('ix_site_page_coverage_domain_id','site_page_coverage',['domain_id'])

def downgrade():
    op.drop_table('site_page_coverage');op.drop_table('site_refresh_policies')
