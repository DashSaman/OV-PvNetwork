"""backup retention setting

Revision ID: h0a1b2c3d4e5
Revises: g9a0b1c2d3e4
Create Date: 2026-09-25

PVN-1020: admin-configurable automatic backup retention (default 10 days).
"""
from alembic import op
import sqlalchemy as sa

revision = "h0a1b2c3d4e5"
down_revision = "g9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "security_settings",
        sa.Column("backup_retention_days", sa.Integer(), nullable=False, server_default="10"),
    )


def downgrade() -> None:
    op.drop_column("security_settings", "backup_retention_days")
