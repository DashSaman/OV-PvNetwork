"""AnyConnect credential foundation

Revision ID: a9c0d1e2f3b4
Revises: b6c7d8e9f0a1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9c0d1e2f3b4"
down_revision: Union[str, None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "anyconnect_credentials",
        sa.Column("user_uuid", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("password_changed_at", sa.BigInteger(), nullable=False),
        sa.Column("last_authenticated_at", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_uuid"],
            ["users.uuid"],
            name="fk_anyconnect_credentials_user_uuid_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_uuid",
            name="anyconnect_credentials_pkey",
        ),
    )
    op.create_index(
        "ix_anyconnect_credentials_enabled",
        "anyconnect_credentials",
        ["enabled"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_anyconnect_credentials_enabled",
        table_name="anyconnect_credentials",
    )
    op.drop_table("anyconnect_credentials")
