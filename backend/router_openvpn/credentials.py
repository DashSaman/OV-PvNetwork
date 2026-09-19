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


def rotate_router_credential(
    db: Session,
    *,
    user_uuid: str,
    node_id: int,
) -> dict:
    """Rotate a credential and return the new plaintext exactly to this caller."""
    router_username = generate_router_username(user_uuid, node_id)
    plaintext = secrets.token_urlsafe(24)
    verifier = hash_router_password(plaintext)
    now = int(time.time())

    key = (str(user_uuid), int(node_id))
    row = db.get(RouterOpenVpnCredential, key)
    if row is None:
        row = RouterOpenVpnCredential(
            user_uuid=str(user_uuid),
            node_id=int(node_id),
            router_username=router_username,
            password_hash=verifier,
            enabled=True,
            created_at=now,
            updated_at=now,
            password_changed_at=now,
            last_authenticated_at=None,
        )
        db.add(row)
    else:
        row.router_username = router_username
        row.password_hash = verifier
        row.enabled = True
        row.updated_at = now
        row.password_changed_at = now

    db.flush()
    result = {
        "router_username": router_username,
        "password": plaintext,
        "enabled": True,
    }
    del plaintext
    return result
