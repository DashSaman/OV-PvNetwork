from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from .models import Base


class AccountDevice(Base):
    __tablename__ = "account_devices"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    device_uuid = Column(
        String(64),
        nullable=False,
    )

    user_uuid = Column(
        String,
        ForeignKey(
            "users.uuid",
            name="fk_account_devices_user_uuid_users",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    name = Column(
        String(255),
        nullable=True,
    )

    device_type = Column(
        String(64),
        nullable=False,
        default="generic",
        server_default="generic",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at = Column(
        BigInteger,
        nullable=False,
    )

    updated_at = Column(
        BigInteger,
        nullable=False,
    )

    last_seen_at = Column(
        BigInteger,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "device_uuid",
            name="uq_account_devices_device_uuid",
        ),
        Index(
            "ix_account_devices_user_uuid",
            "user_uuid",
        ),
    )


class DeviceCredential(Base):
    __tablename__ = "device_credentials"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    credential_uuid = Column(
        String(64),
        nullable=False,
    )

    user_uuid = Column(
        String,
        ForeignKey(
            "users.uuid",
            name="fk_device_credentials_user_uuid_users",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    device_id = Column(
        BigInteger,
        ForeignKey(
            "account_devices.id",
            name="fk_device_credentials_device_id_devices",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    protocol = Column(
        String(64),
        nullable=False,
    )

    credential_type = Column(
        String(64),
        nullable=False,
    )

    external_ref = Column(
        String(255),
        nullable=True,
    )

    secret_ciphertext = Column(
        Text,
        nullable=True,
    )

    secret_kid = Column(
        String(128),
        nullable=True,
    )

    secret_version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at = Column(
        BigInteger,
        nullable=False,
    )

    updated_at = Column(
        BigInteger,
        nullable=False,
    )

    rotated_at = Column(
        BigInteger,
        nullable=True,
    )

    revoked_at = Column(
        BigInteger,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "credential_uuid",
            name="uq_device_credentials_credential_uuid",
        ),
        Index(
            "ix_device_credentials_user_uuid",
            "user_uuid",
        ),
        Index(
            "ix_device_credentials_device_id",
            "device_id",
        ),
        Index(
            "ix_device_credentials_protocol",
            "protocol",
        ),
    )


class AccountProtocolEntitlement(Base):
    __tablename__ = "account_protocol_entitlements"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_uuid = Column(
        String,
        ForeignKey(
            "users.uuid",
            name="fk_account_protocol_entitlements_user_uuid_users",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    protocol = Column(
        String(64),
        nullable=False,
    )

    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at = Column(
        BigInteger,
        nullable=False,
    )

    updated_at = Column(
        BigInteger,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_uuid",
            "protocol",
            name="uq_account_protocol_entitlements_user_protocol",
        ),
        Index(
            "ix_account_protocol_entitlements_user_uuid",
            "user_uuid",
        ),
    )


class AccountPreference(Base):
    __tablename__ = "account_preferences"

    user_uuid = Column(
        String,
        ForeignKey(
            "users.uuid",
            name="fk_account_preferences_user_uuid_users",
            ondelete="CASCADE",
        ),
        primary_key=True,
        nullable=False,
    )

    locale = Column(
        String(32),
        nullable=False,
        default="en-US",
        server_default="en-US",
    )

    timezone = Column(
        String(64),
        nullable=True,
    )

    created_at = Column(
        BigInteger,
        nullable=False,
    )

    updated_at = Column(
        BigInteger,
        nullable=False,
    )
