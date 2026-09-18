"""PVNetwork universal account additive foundation.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""

from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        "account_devices",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "device_uuid",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "user_uuid",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "device_type",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'generic'"),
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),

        sa.Column(
            "created_at",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "last_seen_at",
            sa.BigInteger(),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["user_uuid"],
            ["users.uuid"],
            name="fk_account_devices_user_uuid_users",
            ondelete="CASCADE",
        ),

        sa.UniqueConstraint(
            "device_uuid",
            name="uq_account_devices_device_uuid",
        ),
    )

    op.create_index(
        "ix_account_devices_user_uuid",
        "account_devices",
        ["user_uuid"],
        unique=False,
    )


    op.create_table(
        "device_credentials",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "credential_uuid",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "user_uuid",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "device_id",
            sa.BigInteger(),
            nullable=True,
        ),

        sa.Column(
            "protocol",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "credential_type",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "external_ref",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "secret_ciphertext",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "secret_kid",
            sa.String(length=128),
            nullable=True,
        ),

        sa.Column(
            "secret_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),

        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),

        sa.Column(
            "created_at",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "rotated_at",
            sa.BigInteger(),
            nullable=True,
        ),

        sa.Column(
            "revoked_at",
            sa.BigInteger(),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["user_uuid"],
            ["users.uuid"],
            name="fk_device_credentials_user_uuid_users",
            ondelete="CASCADE",
        ),

        sa.ForeignKeyConstraint(
            ["device_id"],
            ["account_devices.id"],
            name="fk_device_credentials_device_id_devices",
            ondelete="CASCADE",
        ),

        sa.UniqueConstraint(
            "credential_uuid",
            name="uq_device_credentials_credential_uuid",
        ),
    )

    op.create_index(
        "ix_device_credentials_user_uuid",
        "device_credentials",
        ["user_uuid"],
        unique=False,
    )

    op.create_index(
        "ix_device_credentials_device_id",
        "device_credentials",
        ["device_id"],
        unique=False,
    )

    op.create_index(
        "ix_device_credentials_protocol",
        "device_credentials",
        ["protocol"],
        unique=False,
    )


    op.create_table(
        "account_protocol_entitlements",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "user_uuid",
            sa.String(),
            nullable=False,
        ),

        sa.Column(
            "protocol",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),

        sa.Column(
            "created_at",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["user_uuid"],
            ["users.uuid"],
            name="fk_account_protocol_entitlements_user_uuid_users",
            ondelete="CASCADE",
        ),

        sa.UniqueConstraint(
            "user_uuid",
            "protocol",
            name="uq_account_protocol_entitlements_user_protocol",
        ),
    )

    op.create_index(
        "ix_account_protocol_entitlements_user_uuid",
        "account_protocol_entitlements",
        ["user_uuid"],
        unique=False,
    )


    op.create_table(
        "account_preferences",

        sa.Column(
            "user_uuid",
            sa.String(),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "locale",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'en-US'"),
        ),

        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["user_uuid"],
            ["users.uuid"],
            name="fk_account_preferences_user_uuid_users",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:

    op.drop_table(
        "account_preferences"
    )

    op.drop_index(
        "ix_account_protocol_entitlements_user_uuid",
        table_name="account_protocol_entitlements",
    )

    op.drop_table(
        "account_protocol_entitlements"
    )

    op.drop_index(
        "ix_device_credentials_protocol",
        table_name="device_credentials",
    )

    op.drop_index(
        "ix_device_credentials_device_id",
        table_name="device_credentials",
    )

    op.drop_index(
        "ix_device_credentials_user_uuid",
        table_name="device_credentials",
    )

    op.drop_table(
        "device_credentials"
    )

    op.drop_index(
        "ix_account_devices_user_uuid",
        table_name="account_devices",
    )

    op.drop_table(
        "account_devices"
    )
