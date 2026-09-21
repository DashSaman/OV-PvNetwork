from __future__ import annotations

import json
import secrets
import time
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.db.models import UserLifecycleLock, UserRenameJob
from backend.user_rename.contracts import RenameState, TERMINAL_RENAME_STATES, normalize_rename_username


class LifecycleLocked(RuntimeError):
    pass


def create_rename_job(
    db,
    *,
    user_uuid: str,
    old_name: str,
    new_name: str,
    actor: str,
    actor_type: str,
    snapshot: dict | None = None,
) -> UserRenameJob:
    now = int(time.time())
    row = UserRenameJob(
        id=str(uuid4()),
        user_uuid=user_uuid,
        old_name=old_name,
        new_name=normalize_rename_username(new_name),
        state=RenameState.QUEUED.value,
        actor=str(actor)[:128],
        actor_type=str(actor_type)[:32],
        snapshot_json=json.dumps(snapshot or {}, sort_keys=True, separators=(",", ":")),
        evidence_json="{}",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    return row


def acquire_lifecycle_lock(
    db,
    user_uuid: str,
    operation: str,
    job_id: str | None,
    *,
    expires_at: int | None = None,
) -> UserLifecycleLock:
    token = secrets.token_urlsafe(24)
    if get_active_lock(db, user_uuid) is not None:
        raise LifecycleLocked(f"User lifecycle is already locked: {user_uuid}")
    row = UserLifecycleLock(
        user_uuid=user_uuid,
        operation=str(operation)[:32],
        owner_token=token,
        job_id=job_id,
        acquired_at=int(time.time()),
        expires_at=expires_at,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise LifecycleLocked(f"User lifecycle is already locked: {user_uuid}") from exc
    return row


def get_active_lock(db, user_uuid: str) -> UserLifecycleLock | None:
    return db.query(UserLifecycleLock).filter(UserLifecycleLock.user_uuid == user_uuid).first()


def release_lifecycle_lock(db, user_uuid: str, owner_token: str) -> bool:
    row = db.query(UserLifecycleLock).filter(UserLifecycleLock.user_uuid == user_uuid).first()
    if row is None:
        return False
    if row.owner_token != owner_token:
        raise LifecycleLocked("Lifecycle lock owner token mismatch")
    db.delete(row)
    db.flush()
    return True


def claim_runnable_job(db) -> UserRenameJob | None:
    return (
        db.query(UserRenameJob)
        .filter(~UserRenameJob.state.in_(TERMINAL_RENAME_STATES))
        .order_by(UserRenameJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )


def get_rename_job(db, job_id: str) -> UserRenameJob | None:
    return db.query(UserRenameJob).filter(UserRenameJob.id == job_id).first()
