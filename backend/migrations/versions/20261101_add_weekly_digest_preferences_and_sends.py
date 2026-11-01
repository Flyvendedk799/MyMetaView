"""Add weekly digest preferences to users and create weekly_digest_sends table.

Revision ID: 20261101_weekly_digest
Revises: 20251001_brand_font_auto
Create Date: 2026-11-01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261101_weekly_digest"
down_revision = "20251001_brand_font_auto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add weekly_digest_enabled to users table
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "weekly_digest_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )

    # Create weekly_digest_sends table for duplicate send prevention
    op.create_table(
        "weekly_digest_sends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("iso_week", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "year", "iso_week", name="uq_weekly_digest_send_user_week"),
    )
    with op.batch_alter_table("weekly_digest_sends") as batch:
        batch.create_index("ix_weekly_digest_sends_id", ["id"], unique=False)
        batch.create_index("ix_weekly_digest_sends_user_id", ["user_id"], unique=False)
        batch.create_index("ix_weekly_digest_sends_year", ["year"], unique=False)
        batch.create_index("ix_weekly_digest_sends_iso_week", ["iso_week"], unique=False)


def downgrade() -> None:
    op.drop_table("weekly_digest_sends")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("weekly_digest_enabled")
