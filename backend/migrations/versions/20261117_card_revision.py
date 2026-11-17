"""Version card writes to reject stale renders."""
from alembic import op
import sqlalchemy as sa
revision = "20261117_card_revision"
down_revision = "20261101_weekly_digest"
branch_labels = depends_on = None

def upgrade():
    op.add_column("previews", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))

def downgrade():
    op.drop_column("previews", "revision")
