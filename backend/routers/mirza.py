from __future__ import annotations

import hmac
import os
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import config
from backend.db import crud
from backend.db.engine import get_db
from backend.logger import logger
from backend.operations.daily_checks import reset_shared_user_usage
from backend.operations.user_renewal import build_renewal_plan
from backend.routers.anyconnect import provision_new_user_if_enabled
from backend.node.assignment import (
    validate_node_ids,
    set_user_nodes,
    clear_user_nodes,
    get_user_nodes,
    create_user_on_assigned_nodes,
    change_user_status_on_assigned_nodes,
    delete_user_on_assigned_nodes,
)


router = APIRouter(
    prefix="/integrations/mirza",
    tags=["Mirza Integration"],
)


class MirzaCreateUser(BaseModel):
    username: Optional[str] = None
    name: Optional[str] = None
    data_limit: int = Field(ge=0)
    expire: int = Field(gt=0)
    node_ids: Optional[list[int]] = None
    # MIRZA_DEFAULT_SINGLE_USER_V1
    device_limit: int = Field(default=1, ge=0)
    anyconnect_enabled: Optional[bool] = None


class MirzaUpdateUser(BaseModel):
    data_limit: Optional[int] = Field(default=None, ge=0)
    expire: Optional[int] = Field(default=None, gt=0)
    status: Optional[bool] = None
    reset_usage: bool = False


class MirzaRenewUser(BaseModel):
    duration_days: int = Field(default=30, ge=1, le=3650)
    traffic_action: str = Field(default="preserve", pattern="^(preserve|reset|add)$")
    add_traffic: int = Field(default=0, ge=0)


class MirzaStatusRequest(BaseModel):
    status: bool


def require_mirza_key(
    x_mirza_key: str = Header(..., alias="X-Mirza-Key"),
) -> str:
    expected = (config.MIRZA_API_KEY or "").strip()

    if len(expected) < 32:
        logger.error("MIRZA_API_KEY is missing or invalid")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mirza integration is not configured",
        )

    if not hmac.compare_digest(x_mirza_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid integration key",
        )

    return x_mirza_key


def normalize_username(value: Optional[str]) -> str:
    username = (value or "").strip()

    if not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Username must be 3-64 characters and contain only "
                "letters, numbers, underscore or hyphen"
            ),
        )

    return username


def epoch_to_date(timestamp: int):
    try:
        return datetime.fromtimestamp(
            int(timestamp),
            tz=timezone.utc,
        ).date()
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid expire timestamp",
        )


def subscription_url(user) -> str:
    prefix = (
        config.SUBSCRIPTION_URL_PREFIX
        or "https://vpn.example.com"
    ).rstrip("/")

    path = config.SUBSCRIPTION_PATH.strip("/")

    return f"{prefix}/{path}/{user.uuid}"


def serialize_user(user, db: Session) -> dict:
    used = int(user.used or 0)
    total = int(user.total or 0)
    today = datetime.now(timezone.utc).date()

    if user.expiry_date < today:
        user_status = "expired"
    elif total > 0 and used >= total:
        user_status = "limited"
    elif not user.is_active:
        user_status = "disabled"
    else:
        user_status = "active"

    assigned_nodes = get_user_nodes(
        db,
        user.uuid,
        active_only=False,
    )

    nodes = [
        node.name
        for node in assigned_nodes
        if node.status
    ]

    node_ids = [
        node.id
        for node in assigned_nodes
    ]

    return {
        "username": user.name,
        "uuid": user.uuid,
        "status": user_status,
        "enabled": bool(user.is_active),
        "data_limit": total,
        "used_traffic": used,
        "expire": int(
            datetime.combine(
                user.expiry_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            ).timestamp()
        ),
        "expiry_date": user.expiry_date.isoformat(),
        "subscription_url": subscription_url(user),
        "nodes": nodes,
        "node_ids": node_ids,
        "links": [],
        "online_at": None,
        "data_limit_reset": "no_reset",
    }


@router.get("/health")
async def mirza_health(
    db: Session = Depends(get_db),
    _: str = Depends(require_mirza_key),
):
    return {
        "success": True,
        "service": "pvnetwork-panel-mirza-integration",
        "nodes": len(crud.get_all_nodes(db)),
    }


@router.post("/users")
async def create_mirza_user(
    request: MirzaCreateUser,
    db: Session = Depends(get_db),
    _: str = Depends(require_mirza_key),
):
    username = normalize_username(
        request.username or request.name
    )

    existing = crud.get_user_by_name(db, username)

    # درخواست‌های تکراری پرداخت، کاربر را دوباره ایجاد نمی‌کنند.
    if existing:
        return {
            "success": True,
            "created": False,
            "message": "User already exists",
            "data": serialize_user(existing, db),
        }

    expiry_date = epoch_to_date(request.expire)

    try:
        selected_node_ids = validate_node_ids(
            db,
            request.node_ids,
        )
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exception),
        )

    create_request = SimpleNamespace(
        name=username,
        total=int(request.data_limit),
        expiry_date=expiry_date,
        device_limit=int(request.device_limit),
    )

    try:
        user = crud.create_user(
            db,
            create_request,
            owner="mirza",
            commit=False,
        )

        user.used = 0
        user.last_node_usage = 0
        user.is_active = True

        provision_new_user_if_enabled(
            db,
            user.uuid,
            request.anyconnect_enabled,
        )

        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    set_user_nodes(
        db,
        user.uuid,
        selected_node_ids,
    )

    try:
        await create_user_on_assigned_nodes(
            user.uuid,
            user.name,
            db,
        )
    except Exception as exception:
        logger.exception(
            f"Could not create Mirza user on assigned nodes: "
            f"{username}"
        )

        clear_user_nodes(
            db,
            user.uuid,
        )

        crud.delete_user(
            db,
            user.name,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "User could not be created on assigned nodes: "
                + str(exception)
            ),
        )

    logger.info(
        f"Mirza created user on assigned nodes: {username}"
    )

    return {
        "success": True,
        "created": True,
        "message": "User created successfully",
        "data": serialize_user(user, db),
    }


@router.get("/users/{username}")
async def get_mirza_user(
    username: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_mirza_key),
):
    username = normalize_username(username)
    user = crud.get_user_by_name(db, username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {
        "success": True,
        "data": serialize_user(user, db),
    }


@router.put("/users/{username}")
async def update_mirza_user(
    username: str,
    request: MirzaUpdateUser,
    db: Session = Depends(get_db),
    _: str = Depends(require_mirza_key),
):
    username = normalize_username(username)
    user = crud.get_user_by_name(db, username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if request.data_limit is not None:
        user.total = int(request.data_limit)

    if request.expire is not None:
        user.expiry_date = epoch_to_date(request.expire)

    if request.reset_usage:
        await reset_shared_user_usage(
            user,
            db,
        )

    used = int(user.used or 0)
    total = int(user.total or 0)
    today = datetime.now(timezone.utc).date()

    allowed_by_limits = (
        user.expiry_date >= today
        and (total == 0 or total > used)
    )

    if request.status is None:
        new_status = allowed_by_limits
    else:
        new_status = bool(request.status) and allowed_by_limits

    user.is_active = new_status
    db.commit()
    db.refresh(user)

    try:
        await change_user_status_on_assigned_nodes(
            user.uuid,
            user.name,
            new_status,
            db,
        )
    except Exception:
        logger.exception(
            f"Could not synchronize status for Mirza user: {username}"
        )

    return {
        "success": True,
        "message": "User updated successfully",
        "data": serialize_user(user, db),
    }


@router.post("/users/{username}/renew")
async def renew_mirza_user(
    username: str,
    request: MirzaRenewUser,
    db: Session = Depends(get_db),
    _: str = Depends(require_mirza_key),
):
    username = normalize_username(username)
    user = crud.get_user_by_name(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        plan = build_renewal_plan(
            today=datetime.now(timezone.utc).date(),
            current_expiry=user.expiry_date,
            total=int(user.total or 0),
            used=int(user.used or 0),
            duration_days=request.duration_days,
            traffic_action=request.traffic_action,
            add_traffic=request.add_traffic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if request.traffic_action == "reset":
        await reset_shared_user_usage(user, db)
    user.expiry_date = plan.expiry_date
    user.total = plan.total
    user.used = plan.used
    user.is_active = True
    db.commit()
    db.refresh(user)

    node_sync = await change_user_status_on_assigned_nodes(
        user.uuid, user.name, True, db
    )
    logger.info(
        f"Mirza renewed user: {username}; "
        f"expiry={user.expiry_date}; node_sync={node_sync}"
    )
    return {
        "success": True,
        "message": "User renewed successfully",
        "node_sync": bool(node_sync),
        "data": serialize_user(user, db),
    }


@router.put("/users/{username}/status")
async def change_mirza_user_status(
    username: str,
    request: MirzaStatusRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_mirza_key),
):
    username = normalize_username(username)
    user = crud.get_user_by_name(db, username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await change_user_status_on_assigned_nodes(
        user.uuid,
        user.name,
        request.status,
        db,
    )

    user = crud.get_user_by_name(db, username)

    return {
        "success": True,
        "message": "User status changed successfully",
        "data": serialize_user(user, db),
    }


@router.post("/users/{username}/reset")
async def reset_mirza_user_usage(
    username: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_mirza_key),
):
    username = normalize_username(username)
    user = crud.get_user_by_name(db, username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await reset_shared_user_usage(
        user,
        db,
    )

    return {
        "success": True,
        "message": "User usage reset successfully",
        "data": serialize_user(user, db),
    }


@router.delete("/users/{username}")
async def delete_mirza_user(
    username: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_mirza_key),
):
    username = normalize_username(username)
    user = crud.get_user_by_name(db, username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        await delete_user_on_assigned_nodes(user.uuid, user.name, db)
    except Exception:
        logger.exception(
            f"Could not delete Mirza user from every node: {username}"
        )

    crud.delete_user(db, user.name)

    return {
        "success": True,
        "message": "User deleted successfully",
        "username": username,
    }


# ============================================================
# GLOBAL_SINGLE_SESSION_V1
# Configurable concurrent OpenVPN sessions across assigned nodes.
# ============================================================

import time as _session_time
from datetime import datetime as _SessionDateTime, timezone as _SessionTimezone

from fastapi import (
    Depends as _SessionDepends,
    HTTPException as _SessionHTTPException,
)
from pydantic import (
    BaseModel as _SessionBaseModel,
    Field as _SessionField,
)
from sqlalchemy import text as _session_text
from sqlalchemy.orm import Session as _SessionDB

from backend.db import crud as _session_crud
from backend.db.engine import get_db as _session_get_db
from backend.db.models import Node as _SessionNode
from backend.node.assignment import (
    user_can_access_node as _session_user_can_access_node,
)
from backend.protocol_compat import node_key_header


# If disconnect hook is missed, heartbeat expiration allows
# recovery without leaving a user locked forever.
_SESSION_TTL = 90

# A brand-new connection may be acquired just before OpenVPN rewrites
# its status file.  Snapshot reconciliation must not remove that lock
# until the next complete status cycle has had time to include it.
_SESSION_SNAPSHOT_ACQUIRE_GRACE = 15


class _GlobalSessionRequest(_SessionBaseModel):
    common_name: str = _SessionField(
        min_length=1,
        max_length=128,
    )
    remote_addr: str = _SessionField(
        min_length=1,
        max_length=256,
    )


class _GlobalSessionSnapshotRequest(_SessionBaseModel):
    sessions: list[_GlobalSessionRequest] = _SessionField(
        default_factory=list,
        max_length=4096,
    )


def _ensure_session_table(db: _SessionDB) -> None:
    """
    Compatibility bootstrap.

    Alembic owns the production schema, but keeping this
    here allows the integration to fail safely if the
    session table is ever missing on a fresh environment.
    """

    db.execute(
        _session_text(
            """
            CREATE TABLE IF NOT EXISTS active_sessions (
                session_id VARCHAR(64) PRIMARY KEY,
                user_uuid VARCHAR NOT NULL,
                node_id INTEGER NOT NULL,
                common_name VARCHAR NOT NULL,
                remote_addr VARCHAR NOT NULL,
                acquired_at BIGINT NOT NULL,
                last_seen BIGINT NOT NULL,
                CONSTRAINT uq_active_sessions_identity
                UNIQUE (
                    user_uuid,
                    node_id,
                    common_name,
                    remote_addr
                )
            )
            """
        )
    )

    db.execute(
        _session_text(
            """
            CREATE INDEX IF NOT EXISTS
            ix_active_sessions_last_seen
            ON active_sessions(last_seen)
            """
        )
    )

    db.execute(
        _session_text(
            """
            CREATE INDEX IF NOT EXISTS
            ix_active_sessions_user_uuid
            ON active_sessions(user_uuid)
            """
        )
    )

def _get_session_node(
    db: _SessionDB,
    node_key: str,
):
    node_key = (node_key or "").strip()

    if not node_key:
        raise _SessionHTTPException(
            status_code=401,
            detail="Missing node key",
        )

    node = (
        db.query(_SessionNode)
        .filter(
            _SessionNode.key == node_key,
            _SessionNode.status.is_(True),
        )
        .first()
    )

    if node is None:
        raise _SessionHTTPException(
            status_code=401,
            detail="Invalid node key",
        )

    return node


def _resolve_session_user(
    db: _SessionDB,
    node,
    common_name: str,
    *,
    enforce_limits: bool = True,
):
    suffix = f"-{node.name}"

    if not common_name.endswith(suffix):
        raise _SessionHTTPException(
            status_code=422,
            detail="Client name does not match node",
        )

    username = common_name[:-len(suffix)]

    if not username:
        raise _SessionHTTPException(
            status_code=422,
            detail="Invalid client name",
        )

    user = _session_crud.get_user_by_name(
        db,
        username,
    )

    if user is None:
        raise _SessionHTTPException(
            status_code=404,
            detail="User not found",
        )

    if not _session_user_can_access_node(
        db,
        user.uuid,
        node.id,
    ):
        raise _SessionHTTPException(
            status_code=403,
            detail="User is not assigned to this node",
        )

    if enforce_limits:
        today = _SessionDateTime.now(
            _SessionTimezone.utc
        ).date()

        used = int(user.used or 0)
        total = int(user.total or 0)

        if not user.is_active:
            raise _SessionHTTPException(
                status_code=403,
                detail="User is disabled",
            )

        if user.expiry_date < today:
            raise _SessionHTTPException(
                status_code=403,
                detail="User is expired",
            )

        if total > 0 and used >= total:
            raise _SessionHTTPException(
                status_code=403,
                detail="Traffic limit reached",
            )

    return user


@router.post("/session/node-check")
async def global_session_node_check(
    db: _SessionDB = _SessionDepends(
        _session_get_db
    ),
    node_key: str = _SessionDepends(node_key_header),
):
    node = _get_session_node(
        db,
        node_key,
    )

    _ensure_session_table(db)
    db.commit()

    return {
        "success": True,
        "node_id": node.id,
        "node": node.name,
    }


@router.post("/session/acquire")
async def global_session_acquire(
    request: _GlobalSessionRequest,
    db: _SessionDB = _SessionDepends(
        _session_get_db
    ),
    node_key: str = _SessionDepends(node_key_header),
):
    node = _get_session_node(
        db,
        node_key,
    )

    if getattr(
        node,
        "drain",
        False,
    ):
        raise _SessionHTTPException(
            status_code=403,
            detail="Node is draining",
        )


    user = _resolve_session_user(
        db,
        node,
        request.common_name,
        enforce_limits=True,
    )

    _ensure_session_table(db)

    now = int(_session_time.time())
    cutoff = now - _SESSION_TTL

    #
    # The users row is our per-user transaction lock.
    #
    # PostgreSQL SELECT ... FOR UPDATE guarantees that
    # two nodes trying to acquire a session for the same
    # user are serialized inside the database.
    #
    dialect = db.get_bind().dialect.name

    lock_sql = """
        SELECT device_limit
        FROM users
        WHERE uuid = :user_uuid
    """

    if dialect == "postgresql":
        lock_sql += " FOR UPDATE"

    locked_user = (
        db.execute(
            _session_text(lock_sql),
            {
                "user_uuid": user.uuid,
            },
        )
        .mappings()
        .first()
    )

    if locked_user is None:
        db.rollback()

        raise _SessionHTTPException(
            status_code=404,
            detail="User not found",
        )

    device_limit = int(
        locked_user["device_limit"]
        if locked_user["device_limit"] is not None
        else 1
    )

    if device_limit < 0:
        db.rollback()

        raise _SessionHTTPException(
            status_code=500,
            detail="Invalid device limit",
        )


    #
    # Remove expired locks for this user while the user
    # row lock is still held.
    #
    db.execute(
        _session_text(
            """
            DELETE FROM active_sessions
            WHERE user_uuid = :user_uuid
              AND last_seen < :cutoff
            """
        ),
        {
            "user_uuid": user.uuid,
            "cutoff": cutoff,
        },
    )


    #
    # The exact same OpenVPN connection may retry its
    # acquire request. Treat it as idempotent.
    #
    existing = (
        db.execute(
            _session_text(
                """
                SELECT session_id
                FROM active_sessions
                WHERE user_uuid = :user_uuid
                  AND node_id = :node_id
                  AND common_name = :common_name
                  AND remote_addr = :remote_addr
                """
            ),
            {
                "user_uuid": user.uuid,
                "node_id": node.id,
                "common_name": request.common_name,
                "remote_addr": request.remote_addr,
            },
        )
        .mappings()
        .first()
    )

    if existing is not None:

        db.execute(
            _session_text(
                """
                UPDATE active_sessions
                SET last_seen = :now
                WHERE session_id = :session_id
                """
            ),
            {
                "now": now,
                "session_id": existing["session_id"],
            },
        )

        active_count = int(
            db.execute(
                _session_text(
                    """
                    SELECT COUNT(*)
                    FROM active_sessions
                    WHERE user_uuid = :user_uuid
                    """
                ),
                {
                    "user_uuid": user.uuid,
                },
            ).scalar_one()
        )

        db.commit()

        return {
            "success": True,
            "granted": True,
            "username": user.name,
            "node": node.name,
            "device_limit": device_limit,
            "active_sessions": active_count,
            "existing": True,
        }


    active_count = int(
        db.execute(
            _session_text(
                """
                SELECT COUNT(*)
                FROM active_sessions
                WHERE user_uuid = :user_uuid
                """
            ),
            {
                "user_uuid": user.uuid,
            },
        ).scalar_one()
    )


    #
    # 0 means unlimited.
    #
    if (
        device_limit > 0
        and active_count >= device_limit
    ):

        #
        # Persist stale-session cleanup before rejecting.
        #
        db.commit()

        raise _SessionHTTPException(
            status_code=409,
            detail=(
                "Concurrent VPN session limit reached "
                f"({active_count}/{device_limit})"
            ),
        )


    identity = (
        f"{user.uuid}|"
        f"{node.id}|"
        f"{request.common_name}|"
        f"{request.remote_addr}"
    )

    session_id = (
        __import__("hashlib")
        .sha256(
            identity.encode("utf-8")
        )
        .hexdigest()
    )


    db.execute(
        _session_text(
            """
            INSERT INTO active_sessions (
                session_id,
                user_uuid,
                node_id,
                common_name,
                remote_addr,
                acquired_at,
                last_seen
            )
            VALUES (
                :session_id,
                :user_uuid,
                :node_id,
                :common_name,
                :remote_addr,
                :now,
                :now
            )
            """
        ),
        {
            "session_id": session_id,
            "user_uuid": user.uuid,
            "node_id": node.id,
            "common_name": request.common_name,
            "remote_addr": request.remote_addr,
            "now": now,
        },
    )

    db.commit()

    return {
        "success": True,
        "granted": True,
        "username": user.name,
        "node": node.name,
        "device_limit": device_limit,
        "active_sessions": active_count + 1,
        "existing": False,
    }


@router.post("/session/heartbeat")
async def global_session_heartbeat(
    request: _GlobalSessionRequest,
    db: _SessionDB = _SessionDepends(
        _session_get_db
    ),
    node_key: str = _SessionDepends(node_key_header),
):
    """
    Refresh or recover a real OpenVPN connection.

    Rules:
      device_limit == 0 : unlimited
      device_limit > 0  : never track more than the limit

    A reconnect can temporarily create more than one real
    OpenVPN transport session. Reconciliation keeps only the
    allowed number of central session locks.
    """

    node = _get_session_node(
        db,
        node_key,
    )

    user = _resolve_session_user(
        db,
        node,
        request.common_name,
        enforce_limits=False,
    )

    _ensure_session_table(db)

    now = int(_session_time.time())
    cutoff = now - _SESSION_TTL


    #
    # Serialize heartbeat/acquire for this user.
    #
    dialect = db.get_bind().dialect.name

    lock_sql = """
        SELECT device_limit
        FROM users
        WHERE uuid = :user_uuid
    """

    if dialect == "postgresql":
        lock_sql += " FOR UPDATE"


    locked_user = (
        db.execute(
            _session_text(lock_sql),
            {
                "user_uuid": user.uuid,
            },
        )
        .mappings()
        .first()
    )


    if locked_user is None:

        db.rollback()

        raise _SessionHTTPException(
            status_code=404,
            detail="User not found",
        )


    device_limit = int(
        locked_user["device_limit"]
        if locked_user["device_limit"] is not None
        else 1
    )


    if device_limit < 0:

        db.rollback()

        raise _SessionHTTPException(
            status_code=500,
            detail="Invalid device limit",
        )


    #
    # Remove stale central locks first.
    #
    db.execute(
        _session_text(
            """
            DELETE FROM active_sessions
            WHERE user_uuid = :user_uuid
              AND last_seen < :cutoff
            """
        ),
        {
            "user_uuid": user.uuid,
            "cutoff": cutoff,
        },
    )


    existing = (
        db.execute(
            _session_text(
                """
                SELECT session_id
                FROM active_sessions
                WHERE user_uuid = :user_uuid
                  AND node_id = :node_id
                  AND common_name = :common_name
                  AND remote_addr = :remote_addr
                """
            ),
            {
                "user_uuid": user.uuid,
                "node_id": node.id,
                "common_name":
                    request.common_name,
                "remote_addr":
                    request.remote_addr,
            },
        )
        .mappings()
        .first()
    )


    recovered = False
    ignored_over_limit = False
    pruned_sessions = 0


    if existing is not None:

        current_session_id = str(
            existing["session_id"]
        )

        db.execute(
            _session_text(
                """
                UPDATE active_sessions
                SET last_seen = :now
                WHERE session_id = :session_id
                """
            ),
            {
                "now": now,
                "session_id":
                    current_session_id,
            },
        )


        #
        # If old fail-open/reconnect sessions caused us
        # to exceed the current limit, keep the session
        # that is heartbeating now and the freshest
        # allowed remaining sessions.
        #
        if device_limit > 0:

            session_rows = (
                db.execute(
                    _session_text(
                        """
                        SELECT
                            session_id,
                            last_seen,
                            acquired_at
                        FROM active_sessions
                        WHERE user_uuid = :user_uuid
                          AND last_seen >= :cutoff
                        """
                    ),
                    {
                        "user_uuid":
                            user.uuid,

                        "cutoff":
                            cutoff,
                    },
                )
                .mappings()
                .all()
            )


            ordered = sorted(
                session_rows,
                key=lambda row: (
                    0
                    if str(
                        row["session_id"]
                    ) == current_session_id
                    else 1,

                    -int(
                        row["last_seen"]
                    ),

                    -int(
                        row["acquired_at"]
                    ),
                ),
            )


            keep_ids = {
                str(row["session_id"])
                for row
                in ordered[:device_limit]
            }


            for row in ordered:

                session_id = str(
                    row["session_id"]
                )

                if session_id in keep_ids:
                    continue

                result = db.execute(
                    _session_text(
                        """
                        DELETE FROM active_sessions
                        WHERE session_id = :session_id
                        """
                    ),
                    {
                        "session_id":
                            session_id,
                    },
                )

                pruned_sessions += int(
                    result.rowcount or 0
                )


    else:

        active_count_before = int(
            db.execute(
                _session_text(
                    """
                    SELECT COUNT(*)
                    FROM active_sessions
                    WHERE user_uuid = :user_uuid
                      AND last_seen >= :cutoff
                    """
                ),
                {
                    "user_uuid":
                        user.uuid,

                    "cutoff":
                        cutoff,
                },
            ).scalar_one()
        )


        #
        # A heartbeat for an extra connection must NOT
        # recreate another central lock beyond the limit.
        #
        if (
            device_limit > 0
            and
            active_count_before >= device_limit
        ):

            ignored_over_limit = True

        else:

            identity = (
                f"{user.uuid}|"
                f"{node.id}|"
                f"{request.common_name}|"
                f"{request.remote_addr}"
            )

            session_id = (
                __import__("hashlib")
                .sha256(
                    identity.encode(
                        "utf-8"
                    )
                )
                .hexdigest()
            )


            db.execute(
                _session_text(
                    """
                    INSERT INTO active_sessions (
                        session_id,
                        user_uuid,
                        node_id,
                        common_name,
                        remote_addr,
                        acquired_at,
                        last_seen
                    )
                    VALUES (
                        :session_id,
                        :user_uuid,
                        :node_id,
                        :common_name,
                        :remote_addr,
                        :now,
                        :now
                    )
                    """
                ),
                {
                    "session_id":
                        session_id,

                    "user_uuid":
                        user.uuid,

                    "node_id":
                        node.id,

                    "common_name":
                        request.common_name,

                    "remote_addr":
                        request.remote_addr,

                    "now":
                        now,
                },
            )

            recovered = True


    active_count = int(
        db.execute(
            _session_text(
                """
                SELECT COUNT(*)
                FROM active_sessions
                WHERE user_uuid = :user_uuid
                  AND last_seen >= :cutoff
                """
            ),
            {
                "user_uuid":
                    user.uuid,

                "cutoff":
                    cutoff,
            },
        ).scalar_one()
    )


    db.commit()


    return {
        "success": True,

        "refreshed":
            existing is not None,

        "recovered":
            recovered,

        "ignored_over_limit":
            ignored_over_limit,

        "pruned_sessions":
            pruned_sessions,

        "username":
            user.name,

        "node":
            node.name,

        "active_sessions":
            active_count,

        "device_limit":
            device_limit,

        "over_limit":
            (
                device_limit > 0
                and
                active_count > device_limit
            ),
    }


@router.post("/session/snapshot")
async def global_session_snapshot(
    request: _GlobalSessionSnapshotRequest,
    db: _SessionDB = _SessionDepends(
        _session_get_db
    ),
    node_key: str = _SessionDepends(node_key_header),
):
    """Reconcile central locks with one complete OpenVPN status snapshot.

    Individual heartbeats remain responsible for recovering and enforcing
    sessions.  This authoritative node snapshot removes connections that
    disappeared without a reliable client-disconnect hook, so the UI no
    longer waits for the 90-second fallback TTL.
    """

    node = _get_session_node(
        db,
        node_key,
    )

    _ensure_session_table(db)

    now = int(_session_time.time())
    cutoff = now - _SESSION_TTL
    grace_cutoff = (
        now - _SESSION_SNAPSHOT_ACQUIRE_GRACE
    )

    live_identities = {
        (
            item.common_name.strip(),
            item.remote_addr.strip(),
        )
        for item in request.sessions
    }

    rows = (
        db.execute(
            _session_text(
                """
                SELECT
                    session_id,
                    common_name,
                    remote_addr,
                    acquired_at
                FROM active_sessions
                WHERE node_id = :node_id
                """
            ),
            {
                "node_id": node.id,
            },
        )
        .mappings()
        .all()
    )

    refreshed = 0
    pruned = 0

    for row in rows:
        identity = (
            str(row["common_name"]),
            str(row["remote_addr"]),
        )

        if identity in live_identities:
            result = db.execute(
                _session_text(
                    """
                    UPDATE active_sessions
                    SET last_seen = :now
                    WHERE node_id = :node_id
                      AND session_id = :session_id
                    """
                ),
                {
                    "now": now,
                    "node_id": node.id,
                    "session_id": row["session_id"],
                },
            )
            refreshed += int(
                result.rowcount or 0
            )
            continue

        if int(row["acquired_at"]) > grace_cutoff:
            continue

        result = db.execute(
            _session_text(
                """
                DELETE FROM active_sessions
                WHERE node_id = :node_id
                  AND session_id = :session_id
                """
            ),
            {
                "node_id": node.id,
                "session_id": row["session_id"],
            },
        )
        pruned += int(
            result.rowcount or 0
        )

    active_count = int(
        db.execute(
            _session_text(
                """
                SELECT COUNT(*)
                FROM active_sessions
                WHERE node_id = :node_id
                  AND last_seen >= :cutoff
                """
            ),
            {
                "node_id": node.id,
                "cutoff": cutoff,
            },
        ).scalar_one()
    )

    db.commit()

    return {
        "success": True,
        "node": node.name,
        "received": len(live_identities),
        "refreshed": refreshed,
        "pruned": pruned,
        "active_sessions": active_count,
        "acquire_grace_seconds": (
            _SESSION_SNAPSHOT_ACQUIRE_GRACE
        ),
    }


@router.post("/session/release")
async def global_session_release(
    request: _GlobalSessionRequest,
    db: _SessionDB = _SessionDepends(
        _session_get_db
    ),
    node_key: str = _SessionDepends(node_key_header),
):
    node = _get_session_node(
        db,
        node_key,
    )

    user = _resolve_session_user(
        db,
        node,
        request.common_name,
        enforce_limits=False,
    )

    _ensure_session_table(db)

    result = db.execute(
        _session_text(
            """
            DELETE FROM active_sessions
            WHERE user_uuid = :user_uuid
              AND node_id = :node_id
              AND common_name = :common_name
              AND remote_addr = :remote_addr
            """
        ),
        {
            "user_uuid": user.uuid,
            "node_id": node.id,
            "common_name": request.common_name,
            "remote_addr": request.remote_addr,
        },
    )

    db.commit()

    return {
        "success": True,
        "released": result.rowcount > 0,
    }
