"""Add opt-in Router/OpenVPN compatibility metadata.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "node_router_openvpn",
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("port", sa.Integer(), nullable=False, server_default="1195"),
        sa.Column("protocol", sa.String(length=8), nullable=False, server_default="tcp"),
        sa.Column("subnet", sa.String(length=64), nullable=False, server_default="10.9.0.0/24"),
        sa.Column("capability_version", sa.String(length=64), nullable=True),
        sa.Column("last_verified_at", sa.BigInteger(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("port >= 1 AND port <= 65535", name="ck_node_router_openvpn_port_range"),
        sa.CheckConstraint("protocol IN ('tcp', 'udp')", name="ck_node_router_openvpn_protocol"),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("node_id", name="node_router_openvpn_pkey"),
    )
    op.create_table(
        "router_openvpn_credentials",
        sa.Column("user_uuid", sa.String(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("router_username", sa.String(length=27), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("password_changed_at", sa.BigInteger(), nullable=False),
        sa.Column("last_authenticated_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["user_uuid"], ["users.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_uuid", "node_id", name="router_openvpn_credentials_pkey"),
        sa.UniqueConstraint("node_id", "router_username", name="uq_router_openvpn_node_username"),
    )
    op.create_index(
        "ix_router_openvpn_credentials_enabled",
        "router_openvpn_credentials",
        ["enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_router_openvpn_credentials_enabled", table_name="router_openvpn_credentials")
    op.drop_table("router_openvpn_credentials")
    op.drop_table("node_router_openvpn")
