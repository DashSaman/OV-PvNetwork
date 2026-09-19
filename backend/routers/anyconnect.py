from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import string
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user
from backend.db import crud
from backend.db.engine import get_db
from backend.db.models import Node
from backend.node.assignment import user_can_access_node


router = APIRouter(prefix="/anyconnect", tags=["AnyConnect"])
integration_router = APIRouter(
    prefix="/integrations/mirza/anyconnect",
    tags=["AnyConnect Integration"],
)

# OV_ANYCONNECT_USER_TOGGLE_V1
_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024
_PASSWORD_ALPHABET = (
    string.ascii_letters
    + string.digits
    + "-_!@#$%"
)
_CREDENTIAL_KEY_PATH = Path(
    os.getenv(
        "OV_ANYCONNECT_CREDENTIAL_KEY_FILE",
        "/etc/pvnetwork-panel/anyconnect-credential-fernet.key",
    )
)
_PUBLIC_SERVER = os.getenv(
    "OV_ANYCONNECT_PUBLIC_SERVER",
    "vpn.example.com:9443",
).strip() or "vpn.example.com:9443"
_OCCTL_SOCKET = "/run/ocserv/occtl.sock"
_LOCAL_CONTAINER_NAMES = (
    "ov-anyconnect",
    "ov-anyconnect-canary",
)


class AnyConnectPasswordRequest(BaseModel):
    password: Optional[str] = Field(
        default=None,
        min_length=12,
        max_length=64,
    )


class AnyConnectStatusRequest(BaseModel):
    enabled: bool


class AnyConnectSettingsRequest(BaseModel):
    default_enabled: bool


class AnyConnectAuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return (
        "ov-scrypt-v1"
        f"${_SCRYPT_N}"
        f"${_SCRYPT_R}"
        f"${_SCRYPT_P}"
        f"${_encode(salt)}"
        f"${_encode(digest)}"
    )


def _verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = encoded.split("$", 5)
        if scheme != "ov-scrypt-v1":
            return False
        expected = _decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError, OSError):
        return False


def _generate_password(length: int = 20) -> str:
    while True:
        value = "".join(
            secrets.choice(_PASSWORD_ALPHABET)
            for _ in range(length)
        )
        if (
            any(item.islower() for item in value)
            and any(item.isupper() for item in value)
            and any(item.isdigit() for item in value)
            and any(item in "-_!@#$%" for item in value)
        ):
            return value


def _validate_password(password: str) -> str:
    if len(password) < 12 or len(password) > 64:
        raise HTTPException(
            status_code=422,
            detail="AnyConnect password must be 12-64 characters",
        )
    if any(ord(item) < 33 or ord(item) > 126 for item in password):
        raise HTTPException(
            status_code=422,
            detail="AnyConnect password must use visible ASCII characters",
        )
    return password


def _fernet() -> Fernet:
    try:
        key = _CREDENTIAL_KEY_PATH.read_bytes().strip()
        return Fernet(key)
    except (OSError, ValueError) as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AnyConnect credential encryption key is unavailable",
        ) from exception


def _encrypt_password(password: str) -> str:
    return _fernet().encrypt(password.encode("utf-8")).decode("ascii")


def _decrypt_password(ciphertext: Optional[str]) -> Optional[str]:
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(
            str(ciphertext).encode("ascii")
        ).decode("utf-8")
    except (HTTPException, InvalidToken, UnicodeDecodeError, ValueError):
        return None


def _visible_user(db: Session, uuid: str, actor: dict):
    user = crud.get_user_by_uuid(db, uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if actor["type"] == "admin" and user.owner != actor["username"]:
        raise HTTPException(status_code=404, detail="User not found")
    if actor["type"] not in {"admin", "main_admin"}:
        raise HTTPException(status_code=403, detail="Unauthorized access")
    return user


def _credential_row(db: Session, user_uuid: str, *, lock: bool = False):
    statement = """
        SELECT
            user_uuid,
            password_hash,
            password_ciphertext,
            enabled,
            created_at,
            updated_at,
            password_changed_at,
            last_authenticated_at
        FROM anyconnect_credentials
        WHERE user_uuid = :user_uuid
    """
    if lock and db.get_bind().dialect.name == "postgresql":
        statement += " FOR UPDATE"
    return (
        db.execute(
            text(statement),
            {"user_uuid": user_uuid},
        )
        .mappings()
        .first()
    )


def _settings_row(db: Session):
    return (
        db.execute(
            text(
                """
                SELECT id, default_enabled, updated_at, updated_by
                FROM anyconnect_settings
                WHERE id = 1
                """
            )
        )
        .mappings()
        .first()
    )


def get_anyconnect_default_enabled(db: Session) -> bool:
    row = _settings_row(db)
    return bool(row["default_enabled"]) if row else False


def resolve_anyconnect_enabled(
    db: Session,
    requested: Optional[bool],
) -> bool:
    if requested is not None:
        return bool(requested)
    return get_anyconnect_default_enabled(db)


def provision_anyconnect_credential(
    db: Session,
    user_uuid: str,
    *,
    enabled: bool = True,
    password: Optional[str] = None,
    preserve_existing_enabled: bool = False,
) -> dict:
    """Create or rotate one credential without committing the transaction."""
    row = _credential_row(db, user_uuid, lock=True)
    plaintext = _validate_password(password or _generate_password())
    password_hash = _hash_password(plaintext)
    password_ciphertext = _encrypt_password(plaintext)
    now = int(time.time())

    effective_enabled = bool(enabled)
    if row is not None and preserve_existing_enabled:
        effective_enabled = bool(row["enabled"])

    db.execute(
        text(
            """
            INSERT INTO anyconnect_credentials (
                user_uuid,
                password_hash,
                password_ciphertext,
                enabled,
                created_at,
                updated_at,
                password_changed_at
            )
            VALUES (
                :user_uuid,
                :password_hash,
                :password_ciphertext,
                :enabled,
                :now,
                :now,
                :now
            )
            ON CONFLICT (user_uuid)
            DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                password_ciphertext = EXCLUDED.password_ciphertext,
                enabled = EXCLUDED.enabled,
                updated_at = EXCLUDED.updated_at,
                password_changed_at = EXCLUDED.password_changed_at
            """
        ),
        {
            "user_uuid": user_uuid,
            "password_hash": password_hash,
            "password_ciphertext": password_ciphertext,
            "enabled": effective_enabled,
            "now": now,
        },
    )

    return {
        "password": plaintext,
        "enabled": effective_enabled,
        "password_available": True,
    }


def provision_new_user_if_enabled(
    db: Session,
    user_uuid: str,
    requested: Optional[bool],
) -> Optional[dict]:
    enabled = resolve_anyconnect_enabled(db, requested)
    if not enabled:
        return None
    return provision_anyconnect_credential(
        db,
        user_uuid,
        enabled=True,
    )


def subscription_anyconnect_details(
    db: Session,
    user_uuid: str,
    username: str,
) -> Optional[dict]:
    row = _credential_row(db, user_uuid)
    if row is None or not bool(row["enabled"]):
        return None
    password = _decrypt_password(row["password_ciphertext"])
    if not password:
        return None
    return {
        "enabled": True,
        "server": _PUBLIC_SERVER,
        "username": username,
        "password": password,
    }


def _release_anyconnect_sessions(db: Session, user_uuid: str) -> int:
    result = db.execute(
        text(
            """
            DELETE FROM active_sessions
            WHERE user_uuid = :user_uuid
              AND remote_addr LIKE 'ocserv:%'
            """
        ),
        {"user_uuid": user_uuid},
    )
    return int(result.rowcount or 0)


def _disconnect_local_ocserv(username: str) -> bool:
    disconnected = False
    for container in _LOCAL_CONTAINER_NAMES:
        try:
            inspect = subprocess.run(
                ["docker", "inspect", container],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
            if inspect.returncode != 0:
                continue
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "/usr/local/bin/occtl",
                    "-s",
                    _OCCTL_SOCKET,
                    "disconnect",
                    "user",
                    username,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
            disconnected = disconnected or result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            continue
    return disconnected


def _gateway_state() -> dict:
    docker_ready = Path(
        "/etc/pvnetwork-panel/anyconnect-docker-canary.env"
    ).is_file()
    gateway_ready = Path(
        "/etc/pvnetwork-panel/anyconnect-gateway.env"
    ).is_file()
    return {
        "docker_ready": docker_ready,
        "gateway_ready": gateway_ready,
    }


@router.get("/health")
async def anyconnect_health(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    return {
        "success": True,
        "credential_store_ready": True,
        "credential_encryption_ready": _CREDENTIAL_KEY_PATH.is_file(),
        "public_server": _PUBLIC_SERVER,
        "default_enabled": get_anyconnect_default_enabled(db),
        **_gateway_state(),
    }


@router.get("/settings")
async def get_anyconnect_settings(
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    if actor["type"] not in {"admin", "main_admin"}:
        raise HTTPException(status_code=403, detail="Unauthorized access")
    row = _settings_row(db)
    return {
        "success": True,
        "data": {
            "default_enabled": bool(
                row["default_enabled"] if row else False
            ),
            "updated_at": int(row["updated_at"] or 0) if row else 0,
            "updated_by": row["updated_by"] if row else None,
        },
    }


@router.put("/settings")
async def update_anyconnect_settings(
    request: AnyConnectSettingsRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    if actor["type"] != "main_admin":
        raise HTTPException(status_code=403, detail="Main admin access required")
    now = int(time.time())
    db.execute(
        text(
            """
            INSERT INTO anyconnect_settings (
                id, default_enabled, updated_at, updated_by
            )
            VALUES (1, :default_enabled, :now, :updated_by)
            ON CONFLICT (id)
            DO UPDATE SET
                default_enabled = EXCLUDED.default_enabled,
                updated_at = EXCLUDED.updated_at,
                updated_by = EXCLUDED.updated_by
            """
        ),
        {
            "default_enabled": bool(request.default_enabled),
            "now": now,
            "updated_by": str(actor.get("username") or "main_admin"),
        },
    )
    db.commit()
    return {
        "success": True,
        "data": {
            "default_enabled": bool(request.default_enabled),
            "updated_at": now,
        },
    }


@router.get("/users/{uuid}")
async def get_anyconnect_credential_status(
    uuid: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    user = _visible_user(db, uuid, actor)
    row = _credential_row(db, user.uuid)
    return {
        "success": True,
        "data": {
            "user_uuid": user.uuid,
            "username": user.name,
            "configured": row is not None,
            "enabled": bool(row["enabled"]) if row else False,
            "password_available": bool(
                row and row["password_ciphertext"]
            ),
            "password_changed_at": (
                int(row["password_changed_at"])
                if row and row["password_changed_at"] is not None
                else None
            ),
            "last_authenticated_at": (
                int(row["last_authenticated_at"])
                if row and row["last_authenticated_at"] is not None
                else None
            ),
            "server": _PUBLIC_SERVER,
            **_gateway_state(),
        },
    }


@router.get("/users/{uuid}/password")
async def reveal_anyconnect_password(
    uuid: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    user = _visible_user(db, uuid, actor)
    row = _credential_row(db, user.uuid)
    if row is None:
        raise HTTPException(status_code=404, detail="AnyConnect is not configured")
    plaintext = _decrypt_password(row["password_ciphertext"])
    if not plaintext:
        raise HTTPException(
            status_code=409,
            detail="Generate a new AnyConnect password before revealing it",
        )
    return {
        "success": True,
        "data": {
            "username": user.name,
            "server": _PUBLIC_SERVER,
            "password": plaintext,
            "enabled": bool(row["enabled"]),
        },
    }


@router.post("/users/{uuid}/password")
async def rotate_anyconnect_password(
    uuid: str,
    request: AnyConnectPasswordRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    user = _visible_user(db, uuid, actor)
    result = provision_anyconnect_credential(
        db,
        user.uuid,
        enabled=True,
        password=request.password,
        preserve_existing_enabled=True,
    )
    db.commit()

    return {
        "success": True,
        "message": "AnyConnect password created successfully",
        "data": {
            "user_uuid": user.uuid,
            "username": user.name,
            "server": _PUBLIC_SERVER,
            "password": result["password"],
            "enabled": result["enabled"],
            "password_available": True,
            **_gateway_state(),
        },
    }


@router.put("/users/{uuid}/status")
async def change_anyconnect_status(
    uuid: str,
    request: AnyConnectStatusRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    user = _visible_user(db, uuid, actor)
    row = _credential_row(db, user.uuid, lock=True)
    generated_password = None
    released_sessions = 0

    if request.enabled:
        if row is None or not row["password_ciphertext"]:
            generated = provision_anyconnect_credential(
                db,
                user.uuid,
                enabled=True,
            )
            generated_password = generated["password"]
        else:
            db.execute(
                text(
                    """
                    UPDATE anyconnect_credentials
                    SET enabled = TRUE,
                        updated_at = :now
                    WHERE user_uuid = :user_uuid
                    """
                ),
                {
                    "now": int(time.time()),
                    "user_uuid": user.uuid,
                },
            )
    else:
        if row is not None:
            db.execute(
                text(
                    """
                    UPDATE anyconnect_credentials
                    SET enabled = FALSE,
                        updated_at = :now
                    WHERE user_uuid = :user_uuid
                    """
                ),
                {
                    "now": int(time.time()),
                    "user_uuid": user.uuid,
                },
            )
        released_sessions = _release_anyconnect_sessions(db, user.uuid)

    db.commit()
    disconnected_local = False
    if not request.enabled:
        disconnected_local = _disconnect_local_ocserv(user.name)

    return {
        "success": True,
        "data": {
            "user_uuid": user.uuid,
            "username": user.name,
            "server": _PUBLIC_SERVER,
            "configured": bool(request.enabled) or row is not None,
            "enabled": bool(request.enabled),
            "password": generated_password,
            "password_generated": generated_password is not None,
            "password_available": bool(request.enabled) or bool(
                row and row["password_ciphertext"]
            ),
            "released_sessions": released_sessions,
            "local_disconnect_requested": not bool(request.enabled),
            "local_disconnect_succeeded": disconnected_local,
        },
    }


@integration_router.post("/auth")
async def authenticate_anyconnect_user(
    request: AnyConnectAuthRequest,
    db: Session = Depends(get_db),
    x_ov_node_key: str = Header(..., alias="X-OV-Node-Key"),
):
    node_key = (x_ov_node_key or "").strip()
    node = (
        db.query(Node)
        .filter(
            Node.key == node_key,
            Node.status.is_(True),
        )
        .first()
    )
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid node key",
        )
    if getattr(node, "drain", False) or getattr(node, "maintenance", False):
        raise HTTPException(status_code=403, detail="Node is unavailable")

    username = request.username.strip()
    user = crud.get_user_by_name(db, username)
    if user is None or not user_can_access_node(db, user.uuid, node.id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    today = datetime.now(timezone.utc).date()
    used = int(user.used or 0)
    total = int(user.total or 0)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")
    if user.expiry_date < today:
        raise HTTPException(status_code=403, detail="User is expired")
    if total > 0 and used >= total:
        raise HTTPException(status_code=403, detail="Traffic limit reached")

    credential = (
        db.execute(
            text(
                """
                SELECT password_hash, enabled
                FROM anyconnect_credentials
                WHERE user_uuid = :user_uuid
                """
            ),
            {"user_uuid": user.uuid},
        )
        .mappings()
        .first()
    )
    if (
        credential is None
        or not bool(credential["enabled"])
        or not _verify_password(
            request.password,
            str(credential["password_hash"]),
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    db.execute(
        text(
            """
            UPDATE anyconnect_credentials
            SET last_authenticated_at = :now,
                updated_at = :now
            WHERE user_uuid = :user_uuid
            """
        ),
        {
            "now": int(time.time()),
            "user_uuid": user.uuid,
        },
    )
    db.commit()

    return {
        "success": True,
        "user_uuid": user.uuid,
        "username": user.name,
        "node_id": node.id,
        "node": node.name,
        "common_name": f"{user.name}-{node.name}",
        "device_limit": int(
            user.device_limit
            if user.device_limit is not None
            else 1
        ),
    }
