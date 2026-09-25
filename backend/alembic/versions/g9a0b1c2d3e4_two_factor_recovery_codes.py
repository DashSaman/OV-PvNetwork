"""two-factor recovery codes

Revision ID: g9a0b1c2d3e4
Revises: f8a9b0c1d2e3
Create Date: 2026-09-25

PVN-540: one-time 2FA recovery codes, stored as bcrypt hashes.
"""
from alembic import op
import sqlalchemy as sa

revision = "g9a0b1c2d3e4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "two_factor_recovery_codes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("principal_type", sa.String(32), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("used_at", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Index(
            "ix_recovery_principal_unused",
            "username",
            "principal_type",
            "used_at",
        ),
    )


def downgrade() -> None:
    op.drop_table("two_factor_recovery_codes")
