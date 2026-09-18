"""Emergency bandwidth control.

Revision ID: b6c7d8e9f0a1
Revises: a4d6e8f0b2c4
"""

from alembic import op
import sqlalchemy as sa

revision = "b6c7d8e9f0a1"
down_revision = "a4d6e8f0b2c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bandwidth_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("name", name="uq_bandwidth_groups_name"),
    )
    op.create_index("ix_bandwidth_groups_id", "bandwidth_groups", ["id"])

    op.create_table(
        "user_bandwidth_groups",
        sa.Column(
            "user_uuid",
            sa.String(),
            sa.ForeignKey("users.uuid", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("bandwidth_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_user_bandwidth_groups_group_id",
        "user_bandwidth_groups",
        ["group_id"],
    )

    op.create_table(
        "bandwidth_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("target_type", sa.String(length=16), nullable=False, server_default="all"),
        sa.Column(
            "target_group_id",
            sa.Integer(),
            sa.ForeignKey("bandwidth_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_owner", sa.String(length=128), nullable=True),
        sa.Column("target_user_uuids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("node_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("download_kbit", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("expires_at", sa.BigInteger(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_bandwidth_settings_singleton"),
        sa.CheckConstraint(
            "download_kbit >= 64 AND download_kbit <= 10000000",
            name="ck_bandwidth_download_kbit_range",
        ),
        sa.CheckConstraint(
            "target_type IN ('all', 'owner', 'group', 'users')",
            name="ck_bandwidth_target_type",
        ),
    )
    op.execute(
        """
        INSERT INTO bandwidth_settings
            (id, enabled, target_type, target_user_uuids, node_ids,
             download_kbit, revision, updated_at)
        VALUES
            (1, false, 'all', '[]', '[]', 1000, 0, 0)
        """
    )


def downgrade():
    op.drop_table("bandwidth_settings")
    op.drop_index(
        "ix_user_bandwidth_groups_group_id",
        table_name="user_bandwidth_groups",
    )
    op.drop_table("user_bandwidth_groups")
    op.drop_index("ix_bandwidth_groups_id", table_name="bandwidth_groups")
    op.drop_table("bandwidth_groups")
