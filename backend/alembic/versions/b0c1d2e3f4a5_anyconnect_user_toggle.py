"""AnyConnect per-user toggle, encrypted display password and defaults.

Revision ID: b0c1d2e3f4a5
Revises: a9c0d1e2f3b4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9c0d1e2f3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "anyconnect_credentials",
        sa.Column("password_ciphertext", sa.Text(), nullable=True),
    )
    op.alter_column(
        "anyconnect_credentials",
        "enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    )

    op.create_table(
        "anyconnect_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "default_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "updated_at",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_anyconnect_settings_singleton"),
        sa.PrimaryKeyConstraint("id", name="anyconnect_settings_pkey"),
    )
    op.execute(
        """
        INSERT INTO anyconnect_settings (
            id, default_enabled, updated_at, updated_by
        )
        VALUES (1, false, 0, 'migration')
        """
    )


def downgrade() -> None:
    op.drop_table("anyconnect_settings")
    op.alter_column(
        "anyconnect_credentials",
        "enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.true(),
    )
    op.drop_column("anyconnect_credentials", "password_ciphertext")
