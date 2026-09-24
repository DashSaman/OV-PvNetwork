"""One-time Router/OpenVPN credential generation and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import uuid as uuidlib

from sqlalchemy.orm import Session

from backend.db.models import RouterOpenVpnCredential

_SCRYPT_N = 32768
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 128 * 1024 * 1024


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def generate_router_username(user_uuid: str, node_id: int) -> str:
    """Return a deterministic RouterOS-safe username of at most 27 chars."""
    raw_uuid = uuidlib.UUID(str(user_uuid)).bytes
    prefix = base64.b32encode(raw_uuid).decode("ascii").rstrip("=").lower()[:10]
    value = f"r_{prefix}_{int(node_id)}"
    if len(value) > 27:
        raise ValueError("node_id is too large for RouterOS username limit")
    return value


def hash_router_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return "$".join(
        [
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            _b64encode(salt),
            _b64encode(digest),
        ]
    )


def verify_router_password(password: str, encoded: str) -> bool:
    try:
        scheme, n_raw, r_raw, p_raw, salt_raw, digest_raw = str(encoded).split("$", 5)
        if scheme != "scrypt":
            return False
        n, r, p = int(n_raw), int(r_raw), int(p_raw)
        if (n, r, p) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P):
            return False
        expected = _b64decode(digest_raw)
        actual = hashlib.scrypt(
            str(password).encode("utf-8"),
            salt=_b64decode(salt_raw),
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
            maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def prepare_router_credential(*, user_uuid: str, node_id: int) -> dict:
    """Generate a one-time plaintext plus verifier without touching the DB."""
    plaintext = secrets.token_urlsafe(24)
    return {
        "router_username": generate_router_username(user_uuid, node_id),
        "password": plaintext,
        "password_hash": hash_router_password(plaintext),
    }


def persist_router_credential(
    db: Session,
    *,
    user_uuid: str,
    node_id: int,
    router_username: str,
    password_hash: str,
    password_ciphertext: str | None = None,
    enabled: bool = True,
) -> RouterOpenVpnCredential:
    now = int(time.time())
    key = (str(user_uuid), int(node_id))
    row = db.get(RouterOpenVpnCredential, key)
    if row is None:
        row = RouterOpenVpnCredential(
            user_uuid=str(user_uuid),
            node_id=int(node_id),
            router_username=str(router_username),
            password_hash=str(password_hash),
            password_ciphertext=password_ciphertext,
            enabled=bool(enabled),
            created_at=now,
            updated_at=now,
            password_changed_at=now,
            last_authenticated_at=None,
        )
        db.add(row)
    else:
        row.router_username = str(router_username)
        row.password_hash = str(password_hash)
        row.password_ciphertext = password_ciphertext
        row.enabled = bool(enabled)
        row.updated_at = now
        row.password_changed_at = now
    db.flush()
    return row


def rotate_router_credential(
    db: Session,
    *,
    user_uuid: str,
    node_id: int,
) -> dict:
    """Compatibility helper for callers that can persist before remote sync."""
    prepared = prepare_router_credential(user_uuid=user_uuid, node_id=node_id)
    persist_router_credential(
        db,
        user_uuid=user_uuid,
        node_id=node_id,
        router_username=prepared["router_username"],
        password_hash=prepared["password_hash"],
        enabled=True,
    )
    return {
        "router_username": prepared["router_username"],
        "password": prepared["password"],
        "enabled": True,
    }
