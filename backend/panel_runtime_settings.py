from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import jwt
from jwt import InvalidTokenError

from backend.config import config

STATE_ROOT = Path(os.getenv("PVNETWORK_STATE_DIR", "/var/lib/pvnetwork-panel"))
LIVE_ENV = Path(os.getenv("PVNETWORK_ENV_PATH", "/opt/pvnetwork-panel/.env"))
STAGING_ROOT = STATE_ROOT / "panel-settings-staging"
JOB_DIR = STATE_ROOT / "panel-settings-jobs"
TRANSITION_FILE = STATE_ROOT / "panel-path-transition.json"
LOCK_FILE = STATE_ROOT / "panel-settings.lock"
APPLY_HELPER = os.getenv(
    "PVNETWORK_PANEL_SETTINGS_HELPER",
    "/usr/local/sbin/pvnetwork-panel-settings-apply",
)

PATH_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
RESERVED = {"api", "healthz", "doc", "redoc", "openapi.json", "assets"}
SECRET_KEYS = {"current_password", "new_password", "password_hash", "jwt", "token", "env"}


class ApplyBusy(RuntimeError):
    pass


def validate_admin_username(value: str, delegated_names: set[str]) -> str:
    value = value.strip()
    if not 3 <= len(value) <= 64:
        raise ValueError("Username must be 3-64 printable characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("Username must be 3-64 printable characters")
    if value.casefold() in {name.casefold() for name in delegated_names}:
        raise ValueError("Username collides with an existing administrator")
    return value


def validate_panel_path(value: str, subscription_path: str) -> str:
    value = value.strip()
    if not PATH_RE.fullmatch(value):
        raise ValueError("Panel path must be 3-64 letters, digits, '_' or '-'")
    blocked = RESERVED | {subscription_path.casefold()}
    if value.casefold() in blocked:
        raise ValueError("Panel path collides with a reserved route")
    return value


def _render_env_value(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:@$%+\-=]+", value):
        return value
    return json.dumps(value, ensure_ascii=False)


def build_candidate_env(
    live_env: Path,
    new_username: str | None,
    new_password_hash: str | None,
    new_path: str | None,
    new_generation: str | None,
) -> str:
    updates: dict[str, str] = {}
    if new_username is not None:
        updates["ADMIN_USERNAME"] = new_username
    if new_password_hash is not None:
        updates["ADMIN_PASSWORD_HASH"] = new_password_hash
    if new_generation is not None:
        updates["MAIN_ADMIN_AUTH_GENERATION"] = new_generation
    if new_path is not None:
        updates["URLPATH"] = new_path
        updates["VITE_URLPATH"] = new_path

    lines = live_env.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    written: set[str] = set()
    for raw in lines:
        stripped = raw.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key in updates:
            if key not in written:
                out.append(f"{key}={_render_env_value(updates[key])}")
                written.add(key)
            continue
        out.append(raw)
    for key, value in updates.items():
        if key not in written:
            out.append(f"{key}={_render_env_value(value)}")
    return "\n".join(out).rstrip() + "\n"


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in SECRET_KEYS:
                return True
            if _contains_secret_key(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_secret_key(child) for child in value)
    return False


def _atomic_write_json(path: Path, payload: dict) -> None:
    if _contains_secret_key(payload):
        raise ValueError("Secret-bearing keys are forbidden in runtime state")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


def _job_path(change_id: str) -> Path:
    if not JOB_ID_RE.fullmatch(change_id):
        raise ValueError("Invalid change id")
    return JOB_DIR / f"{change_id}.json"


def write_job_state(change_id: str, payload: dict) -> None:
    _atomic_write_json(_job_path(change_id), payload)


def read_job_state(change_id: str) -> dict | None:
    path = _job_path(change_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_transition_state(payload: dict) -> None:
    _atomic_write_json(TRANSITION_FILE, payload)


def load_transition_state() -> dict | None:
    try:
        value = json.loads(TRANSITION_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def mint_change_status_token(change_id: str, ttl_seconds: int = 900) -> str:
    now = int(time.time())
    payload = {
        "typ": "panel-settings-status",
        "cid": change_id,
        "iat": now,
        "exp": now + int(ttl_seconds),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm="HS256")


def verify_change_status_token(token: str, change_id: str) -> None:
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise ValueError("Invalid change status token") from exc
    if payload.get("typ") != "panel-settings-status":
        raise ValueError("Invalid change status token type")
    if payload.get("cid") != change_id:
        raise ValueError("Change status token does not match change id")


def acquire_apply_lock() -> int:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise ApplyBusy("A panel settings change is already active") from exc
    return fd


def spawn_apply_helper(change_id: str, staging_dir: Path, lock_fd: int) -> int:
    if not JOB_ID_RE.fullmatch(change_id):
        raise ValueError("Invalid change id")
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    log_path = JOB_DIR / f"{change_id}.log"
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    log_handle = os.fdopen(log_fd, "ab", buffering=0)
    command = [
        APPLY_HELPER,
        "--change-id",
        change_id,
        "--staging-dir",
        str(staging_dir),
        "--lock-fd",
        str(lock_fd),
    ]
    try:
        process = subprocess.Popen(
            command,
            pass_fds=(lock_fd,),
            start_new_session=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
    finally:
        log_handle.close()
    return int(process.pid)
