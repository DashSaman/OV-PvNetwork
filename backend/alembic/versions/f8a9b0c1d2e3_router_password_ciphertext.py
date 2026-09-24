"""router password ciphertext for admin display

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-24

PVN-1012: store a reversible Fernet ciphertext of the Router/MikroTik
password so the admin panel can display it later. Legacy rows keep NULL
(one-time display only) until the credential is generated or rotated again.
"""
from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "router_openvpn_credentials",
        sa.Column("password_ciphertext", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("router_openvpn_credentials", "password_ciphertext")
