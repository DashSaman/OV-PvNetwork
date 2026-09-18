"""device limit and multi session support

Revision ID: c4b7a1d2e3f4
Revises: 0f7118ad11ee
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4b7a1d2e3f4"
down_revision: Union[str, None] = "0f7118ad11ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    #
    # 0 = unlimited
    # 1 = legacy / current behaviour
    # N = max simultaneous VPN sessions
    #
    op.add_column(
        "users",
        sa.Column(
            "device_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    op.create_check_constraint(
        "ck_users_device_limit_nonnegative",
        "users",
        "device_limit >= 0",
    )


    #
    # Convert active_sessions from:
    #
    #   one row per user
    #
    # into:
    #
    #   many sessions per user
    #
    op.add_column(
        "active_sessions",
        sa.Column(
            "session_id",
            sa.String(length=64),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE active_sessions
            SET session_id = md5(
                user_uuid
                || '|'
                || node_id::text
                || '|'
                || common_name
                || '|'
                || remote_addr
            )
            WHERE session_id IS NULL
            """
        )
    )

    op.alter_column(
        "active_sessions",
        "session_id",
        nullable=False,
    )

    op.drop_constraint(
        "active_sessions_pkey",
        "active_sessions",
        type_="primary",
    )

    op.create_primary_key(
        "active_sessions_pkey",
        "active_sessions",
        ["session_id"],
    )

    op.create_unique_constraint(
        "uq_active_sessions_identity",
        "active_sessions",
        [
            "user_uuid",
            "node_id",
            "common_name",
            "remote_addr",
        ],
    )

    op.create_index(
        "ix_active_sessions_user_uuid",
        "active_sessions",
        ["user_uuid"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_active_sessions_user_uuid_users",
        "active_sessions",
        "users",
        ["user_uuid"],
        ["uuid"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_active_sessions_node_id_nodes",
        "active_sessions",
        "nodes",
        ["node_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:

    connection = op.get_bind()

    #
    # If downgrade happens after multiple sessions were
    # created, retain only the newest session per user
    # so the old user_uuid primary key can be restored.
    #
    connection.execute(
        sa.text(
            """
            DELETE FROM active_sessions AS old
            USING active_sessions AS newer
            WHERE old.user_uuid = newer.user_uuid
              AND (
                    old.last_seen < newer.last_seen
                    OR (
                        old.last_seen = newer.last_seen
                        AND old.session_id < newer.session_id
                    )
                  )
            """
        )
    )

    op.drop_constraint(
        "fk_active_sessions_node_id_nodes",
        "active_sessions",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_active_sessions_user_uuid_users",
        "active_sessions",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_active_sessions_user_uuid",
        table_name="active_sessions",
    )

    op.drop_constraint(
        "uq_active_sessions_identity",
        "active_sessions",
        type_="unique",
    )

    op.drop_constraint(
        "active_sessions_pkey",
        "active_sessions",
        type_="primary",
    )

    op.create_primary_key(
        "active_sessions_pkey",
        "active_sessions",
        ["user_uuid"],
    )

    op.drop_column(
        "active_sessions",
        "session_id",
    )

    op.drop_constraint(
        "ck_users_device_limit_nonnegative",
        "users",
        type_="check",
    )

    op.drop_column(
        "users",
        "device_limit",
    )
