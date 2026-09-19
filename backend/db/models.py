from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, ForeignKey, Index, UniqueConstraint, CheckConstraint, String, Text
from .engine import Base
from datetime import date


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(unique=True, nullable=True)
    name: Mapped[str] = mapped_column(unique=True)
    total: Mapped[int] = mapped_column(BigInteger, nullable=True)
    used: Mapped[int] = mapped_column(BigInteger, nullable=True)
    last_node_usage: Mapped[int] = mapped_column(BigInteger, default=0)
    expiry_date: Mapped[date]
    is_active: Mapped[bool] = mapped_column(default=True)
    owner: Mapped[str] = mapped_column(nullable=False)

    # 0 = unlimited concurrent VPN sessions.
    # Positive values are maximum simultaneous sessions.
    device_limit: Mapped[int] = mapped_column(
        default=1,
        server_default="1",
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "device_limit >= 0",
            name="ck_users_device_limit_nonnegative",
        ),
    )


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    quota_total: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    quota_used: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    # PVNETWORK_RESELLER_UNLIMITED_SLOTS_V2
    unlimited_quota_total: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    unlimited_quota_used: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)

    __table_args__ = (
        CheckConstraint("quota_total >= 0", name="ck_admins_quota_total_nonnegative"),
        CheckConstraint("quota_used >= 0", name="ck_admins_quota_used_nonnegative"),
        CheckConstraint("quota_used <= quota_total", name="ck_admins_quota_within_total"),
        CheckConstraint("unlimited_quota_total >= 0", name="ck_admins_unlimited_total_nonnegative"),
        CheckConstraint("unlimited_quota_used >= 0", name="ck_admins_unlimited_used_nonnegative"),
        CheckConstraint("unlimited_quota_used <= unlimited_quota_total", name="ck_admins_unlimited_within_total"),
    )


class ResellerCreditTransaction(Base):
    __tablename__ = "reseller_credit_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    user_uuid: Mapped[str] = mapped_column(String, nullable=True)
    note: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_reseller_credit_transactions_admin_id", "admin_id"),
        Index("ix_reseller_credit_transactions_created_at", "created_at"),
    )


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column()
    address: Mapped[str] = mapped_column()
    tunnel_address: Mapped[str] = mapped_column(nullable=True)
    protocol: Mapped[str] = mapped_column()
    ovpn_port: Mapped[int] = mapped_column()
    port: Mapped[int] = mapped_column()
    key: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[bool] = mapped_column(default=True)
    drain: Mapped[bool] = mapped_column(default=False)
    weight: Mapped[int] = mapped_column(default=100)
    maintenance: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=True)
    health_score: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    last_upgrade_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    last_upgrade_status: Mapped[str] = mapped_column(String(32), nullable=True)


class UserNode(Base):
    __tablename__ = "user_nodes"

    user_uuid: Mapped[str] = mapped_column(
        ForeignKey("users.uuid", ondelete="CASCADE"),
        primary_key=True,
    )

    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tunnel_address: Mapped[str] = mapped_column(nullable=True)
    port: Mapped[int] = mapped_column(default=1194, nullable=False)
    protocol: Mapped[str] = mapped_column(default="tcp", nullable=False)


# PVNETWORK_ANYCONNECT_USER_TOGGLE_V1
class AnyConnectCredential(Base):
    __tablename__ = "anyconnect_credentials"

    user_uuid: Mapped[str] = mapped_column(
        ForeignKey("users.uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_ciphertext: Mapped[str] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        default=False,
        server_default="false",
        nullable=False,
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    password_changed_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_authenticated_at: Mapped[int] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        Index("ix_anyconnect_credentials_enabled", "enabled"),
    )


class AnyConnectSettings(Base):
    __tablename__ = "anyconnect_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    default_enabled: Mapped[bool] = mapped_column(
        default=False,
        server_default="false",
        nullable=False,
    )
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        server_default="0",
        nullable=False,
    )
    updated_by: Mapped[str] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "id = 1",
            name="ck_anyconnect_settings_singleton",
        ),
    )


class UserNodeUsage(Base):
    """
    Per-node usage baseline for shared
    multi-node traffic accounting.
    """

    __tablename__ = "user_node_usage"

    user_uuid: Mapped[str] = mapped_column(
        ForeignKey(
            "users.uuid",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    node_id: Mapped[int] = mapped_column(
        ForeignKey(
            "nodes.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    last_usage: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )



class ActiveSession(Base):
    """
    One row per active VPN connection.

    device_limit is stored on users:
      0 = unlimited
      N = maximum simultaneous VPN sessions.
    """

    __tablename__ = "active_sessions"

    session_id: Mapped[str] = mapped_column(
        primary_key=True,
    )

    user_uuid: Mapped[str] = mapped_column(
        ForeignKey(
            "users.uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    node_id: Mapped[int] = mapped_column(
        ForeignKey(
            "nodes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    common_name: Mapped[str] = mapped_column(
        nullable=False,
    )

    remote_addr: Mapped[str] = mapped_column(
        nullable=False,
    )

    acquired_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    last_seen: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_uuid",
            "node_id",
            "common_name",
            "remote_addr",
            name="uq_active_sessions_identity",
        ),
        Index(
            "ix_active_sessions_user_uuid",
            "user_uuid",
        ),
        Index(
            "ix_active_sessions_last_seen",
            "last_seen",
        ),
    )


class DomainActivity(Base):
    """Aggregated DNS domains observed for one user on one node."""

    __tablename__ = "domain_activity"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_uuid: Mapped[str] = mapped_column(
        ForeignKey(
            "users.uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    node_id: Mapped[int] = mapped_column(
        ForeignKey(
            "nodes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    domain: Mapped[str] = mapped_column(
        String(253),
        nullable=False,
    )

    first_seen: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    last_seen: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    hit_count: Mapped[int] = mapped_column(
        BigInteger,
        default=1,
        server_default="1",
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_uuid",
            "node_id",
            "domain",
            name="uq_domain_activity_user_node_domain",
        ),
        CheckConstraint(
            "hit_count > 0",
            name="ck_domain_activity_hit_count_positive",
        ),
        CheckConstraint(
            "last_seen >= first_seen",
            name="ck_domain_activity_time_order",
        ),
        Index(
            "ix_domain_activity_user_last_seen",
            "user_uuid",
            "last_seen",
        ),
        Index(
            "ix_domain_activity_node_last_seen",
            "node_id",
            "last_seen",
        ),
    )

class MonitoringSettings(Base):
    __tablename__='monitoring_settings'
    id: Mapped[int]=mapped_column(primary_key=True)
    enabled: Mapped[bool]=mapped_column(default=False,nullable=False)
    telegram_token_encrypted: Mapped[str]=mapped_column(nullable=True)
    telegram_chat_id: Mapped[str]=mapped_column(String(128),nullable=True)
    cpu_limit: Mapped[int]=mapped_column(default=85,nullable=False)
    ram_limit: Mapped[int]=mapped_column(default=85,nullable=False)
    disk_limit: Mapped[int]=mapped_column(default=85,nullable=False)
    node_status_alerts: Mapped[bool]=mapped_column(default=True,nullable=False)
    ssl_host: Mapped[str]=mapped_column(String(255),nullable=True)
    ssl_port: Mapped[int]=mapped_column(default=443,nullable=False)
    ssl_warning_days: Mapped[int]=mapped_column(default=14,nullable=False)
    updated_at: Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
    updated_by: Mapped[str]=mapped_column(String(128),nullable=True)

class AuditLog(Base):
    __tablename__='audit_logs'
    id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    actor: Mapped[str]=mapped_column(String(128),nullable=False); actor_type: Mapped[str]=mapped_column(String(32),nullable=False)
    action: Mapped[str]=mapped_column(String(16),nullable=False); resource: Mapped[str]=mapped_column(String(512),nullable=False)
    status_code: Mapped[int]=mapped_column(nullable=False); success: Mapped[bool]=mapped_column(nullable=False)
    ip_address: Mapped[str]=mapped_column(String(64),nullable=True); user_agent: Mapped[str]=mapped_column(String(512),nullable=True)
    request_id: Mapped[str]=mapped_column(String(64),nullable=False,unique=True); duration_ms: Mapped[int]=mapped_column(nullable=False)
    created_at: Mapped[int]=mapped_column(BigInteger,nullable=False)

class SecuritySettings(Base):
    __tablename__='security_settings'
    id: Mapped[int]=mapped_column(primary_key=True)
    rate_limit_enabled: Mapped[bool]=mapped_column(default=True,nullable=False)
    rate_limit_per_minute: Mapped[int]=mapped_column(default=120,nullable=False)
    ip_allowlist_enabled: Mapped[bool]=mapped_column(default=False,nullable=False)
    allowed_cidrs: Mapped[str]=mapped_column(nullable=False,default='[]')
    updated_at: Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
class PrincipalSecurity(Base):
    __tablename__='principal_security'
    id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    username: Mapped[str]=mapped_column(String(128),nullable=False)
    principal_type: Mapped[str]=mapped_column(String(32),nullable=False)
    totp_secret_encrypted: Mapped[str]=mapped_column(nullable=True)
    totp_enabled: Mapped[bool]=mapped_column(default=False,nullable=False)
    updated_at: Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
    __table_args__=(UniqueConstraint('username','principal_type',name='uq_principal_security'),)
class ApiToken(Base):
    __tablename__='api_tokens'
    id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    name: Mapped[str]=mapped_column(String(128),nullable=False)
    token_prefix: Mapped[str]=mapped_column(String(16),nullable=False)
    token_hash: Mapped[str]=mapped_column(String(64),nullable=False,unique=True)
    scopes: Mapped[str]=mapped_column(nullable=False)
    expires_at: Mapped[int]=mapped_column(BigInteger,nullable=True)
    revoked_at: Mapped[int]=mapped_column(BigInteger,nullable=True)
    created_at: Mapped[int]=mapped_column(BigInteger,nullable=False)
    last_used_at: Mapped[int]=mapped_column(BigInteger,nullable=True)
    created_by: Mapped[str]=mapped_column(String(128),nullable=False)

class UsageHistory(Base):
    __tablename__='usage_history'
    id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    user_uuid: Mapped[str]=mapped_column(ForeignKey('users.uuid',ondelete='CASCADE'),nullable=False)
    used: Mapped[int]=mapped_column(BigInteger,nullable=False)
    total: Mapped[int]=mapped_column(BigInteger,nullable=True)
    sampled_at: Mapped[int]=mapped_column(BigInteger,nullable=False)
    __table_args__=(Index('ix_usage_history_user_time','user_uuid','sampled_at'),)
class NotificationState(Base):
    __tablename__='notification_state'
    key: Mapped[str]=mapped_column(String(255),primary_key=True)
    last_value: Mapped[str]=mapped_column(String(512),nullable=True)
    sent_at: Mapped[int]=mapped_column(BigInteger,nullable=False)



# ============================================================
# PVNETWORK_EMERGENCY_BANDWIDTH_CONTROL_V1
# ============================================================

class BandwidthGroup(Base):
    __tablename__ = "bandwidth_groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class UserBandwidthGroup(Base):
    __tablename__ = "user_bandwidth_groups"

    user_uuid: Mapped[str] = mapped_column(
        ForeignKey("users.uuid", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("bandwidth_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class BandwidthSettings(Base):
    __tablename__ = "bandwidth_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), default="all", server_default="all", nullable=False)
    target_group_id: Mapped[int] = mapped_column(
        ForeignKey("bandwidth_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_owner: Mapped[str] = mapped_column(String(128), nullable=True)
    target_user_uuids: Mapped[str] = mapped_column(Text, default="[]", server_default="[]", nullable=False)
    node_ids: Mapped[str] = mapped_column(Text, default="[]", server_default="[]", nullable=False)
    download_kbit: Mapped[int] = mapped_column(default=1000, server_default="1000", nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_bandwidth_settings_singleton"),
        CheckConstraint(
            "download_kbit >= 64 AND download_kbit <= 10000000",
            name="ck_bandwidth_download_kbit_range",
        ),
        CheckConstraint(
            "target_type IN ('all', 'owner', 'group', 'users')",
            name="ck_bandwidth_target_type",
        ),
    )
