from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import panel_runtime_settings as runtime
from backend.auth.auth import get_current_user, mint_main_admin_token
from backend.auth.hash import hash_password, verify_password
from backend.config import config
from backend.db.engine import get_db
from backend.db.models import Admin, PrincipalSecurity
from backend.schema.output import ResponseModel

router = APIRouter(prefix="/security/panel-settings", tags=["Panel Runtime Settings"])


class PanelSettingsApplyIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_username: str | None = None
    new_password: str | None = None
    new_path: str | None = None


def require_interactive_main_admin(user: dict) -> None:
    if user.get("type") != "main_admin" or user.get("auth_kind") == "api_token":
        raise HTTPException(403, "Interactive main administrator required")


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _http422(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _active_change() -> str | None:
    try:
        files = sorted(runtime.JOB_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    for path in files[:20]:
        try:
            state = runtime.read_job_state(path.stem)
        except Exception:
            continue
        if state and state.get("status") not in {"complete", "rolled_back"}:
            return path.stem
    return None


@router.get("", response_model=ResponseModel)
async def get_panel_settings(user: dict = Depends(get_current_user)):
    require_interactive_main_admin(user)
    transition = runtime.load_transition_state()
    redirect = None
    if transition and int(transition.get("redirect_expires_at") or 0) > int(time.time()):
        redirect = {
            "old_path": transition.get("old_path"),
            "new_path": transition.get("new_path"),
            "redirect_expires_at": transition.get("redirect_expires_at"),
        }
    return ResponseModel(success=True, msg="Panel settings", data={
        "username": config.ADMIN_USERNAME,
        "panel_path": config.URLPATH,
        "redirect": redirect,
        "active_change": _active_change(),
    })


@router.get("/jobs/{change_id}", response_model=ResponseModel)
async def get_panel_settings_job(
    change_id: str,
    change_token: str = Header(alias="X-PVNetwork-Change-Token"),
):
    try:
        runtime.verify_change_status_token(change_token, change_id)
    except ValueError as exc:
        raise HTTPException(401, "Invalid change status token") from exc
    state = runtime.read_job_state(change_id)
    if not state:
        raise HTTPException(404, "Panel settings change not found")
    public = {
        key: state.get(key)
        for key in (
            "change_id", "status", "old_path", "new_path", "old_username",
            "new_username", "changed_fields", "failure_reason", "created_at", "updated_at",
        )
        if key in state
    }
    return ResponseModel(success=True, msg="Panel settings change status", data=public)


@router.post("/apply", response_model=ResponseModel)
async def apply_panel_settings(
    request: PanelSettingsApplyIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    require_interactive_main_admin(user)
    try:
        lock_fd = runtime.acquire_apply_lock()
    except runtime.ApplyBusy as exc:
        raise HTTPException(409, str(exc)) from exc

    staging_dir: Path | None = None
    spawned = False
    try:
        live = _parse_env(runtime.LIVE_ENV)
        current_hash = live.get("ADMIN_PASSWORD_HASH", "")
        if not current_hash or not verify_password(request.current_password, current_hash):
            raise HTTPException(401, "Current password is incorrect")

        old_username = live.get("ADMIN_USERNAME", config.ADMIN_USERNAME)
        old_path = live.get("URLPATH", config.URLPATH)
        old_generation = live.get("MAIN_ADMIN_AUTH_GENERATION", config.MAIN_ADMIN_AUTH_GENERATION)
        subscription_path = live.get("SUBSCRIPTION_PATH", config.SUBSCRIPTION_PATH)
        delegated_names = {row[0] for row in db.query(Admin.username).all()}

        new_username = None
        if request.new_username is not None:
            try:
                candidate = runtime.validate_admin_username(request.new_username, delegated_names)
            except ValueError as exc:
                raise _http422(str(exc)) from exc
            if candidate != old_username:
                new_username = candidate

        new_path = None
        if request.new_path is not None:
            try:
                candidate_path = runtime.validate_panel_path(request.new_path, subscription_path)
            except ValueError as exc:
                raise _http422(str(exc)) from exc
            if candidate_path.casefold() != old_path.casefold():
                new_path = candidate_path

        new_password_hash = None
        password_changed = request.new_password is not None
        if password_changed:
            new_password = request.new_password or ""
            if len(new_password) < 12:
                raise _http422("New password must be at least 12 characters")
            if len(new_password.encode("utf-8")) > 72:
                raise _http422("New password must be at most 72 UTF-8 bytes")
            if verify_password(new_password, current_hash):
                raise _http422("New password must differ from the current password")
            new_password_hash = hash_password(new_password)

        credentials_changed = bool(new_username is not None or password_changed)
        if new_username is None and new_path is None and not password_changed:
            raise _http422("No settings change requested")

        target_username = new_username or old_username
        target_path = new_path or old_path
        target_generation = secrets.token_urlsafe(24) if credentials_changed else old_generation
        candidate_text = runtime.build_candidate_env(
            runtime.LIVE_ENV,
            new_username=new_username,
            new_password_hash=new_password_hash,
            new_path=new_path,
            new_generation=target_generation if credentials_changed else None,
        )

        change_id = secrets.token_urlsafe(18)
        staging_dir = runtime.STAGING_ROOT / change_id
        staging_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        candidate_env = staging_dir / "candidate.env"
        candidate_env.write_text(candidate_text, encoding="utf-8")
        os.chmod(candidate_env, 0o600)

        principal = (
            db.query(PrincipalSecurity)
            .filter_by(username=old_username, principal_type="main_admin")
            .first()
        )
        now = int(time.time())
        changed_fields = []
        if new_username is not None:
            changed_fields.append("username")
        if password_changed:
            changed_fields.append("password")
        if new_path is not None:
            changed_fields.append("path")

        job = {
            "change_id": change_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "expected_env_sha256": _sha256(runtime.LIVE_ENV),
            "old_path": old_path,
            "new_path": target_path,
            "old_username": old_username,
            "new_username": target_username,
            "username_changed": new_username is not None,
            "credentials_changed": credentials_changed,
            "changed_fields": changed_fields,
            "principal_security_id": principal.id if principal else None,
            "failure_reason": None,
            "audit_actor": str(user.get("username") or old_username),
        }
        runtime.write_job_state(change_id, job)
        runtime.spawn_apply_helper(change_id, staging_dir, lock_fd)
        spawned = True
        os.close(lock_fd)

        data = {
            "change_id": change_id,
            "status_token": runtime.mint_change_status_token(change_id),
            "pending_access_token": (
                mint_main_admin_token(target_username, target_generation)
                if credentials_changed else None
            ),
            "target_path": target_path,
        }
        return ResponseModel(success=True, msg="Panel settings change started", data=data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, "Unable to stage panel settings change") from exc
    finally:
        if not spawned:
            try:
                os.close(lock_fd)
            except OSError:
                pass
            if staging_dir is not None:
                shutil.rmtree(staging_dir, ignore_errors=True)
