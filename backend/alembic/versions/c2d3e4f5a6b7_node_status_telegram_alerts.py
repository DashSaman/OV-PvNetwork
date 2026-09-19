"""Add node online/offline Telegram alert toggle.

Revision ID: c2d3e4f5a6b7
Revises: c1d2e3f4a5b6
"""

from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5a6b7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monitoring_settings",
        sa.Column(
            "node_status_alerts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("monitoring_settings", "node_status_alerts")
