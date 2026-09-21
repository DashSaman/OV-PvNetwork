from __future__ import annotations

import json
import secrets
import time
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.db.models import UserLifecycleLock, UserRenameJob
from backend.user_rename.contracts import RenameState, TERMINAL_RENAME_STATES, normalize_rename_username


class LifecycleLocked(RuntimeError):
    def __init__(self, message: str, *, operation: str | None = None, job_id: str | None = None, user_uuid: str | None = None):
        super().__init__(message)
        self.operation = operation
        self.job_id = job_id
        self.user_uuid = user_uuid


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
    existing = get_active_lock(db, user_uuid)
    if existing is not None:
        raise LifecycleLocked(
            f"User lifecycle is already locked: {user_uuid}",
            operation=existing.operation, job_id=existing.job_id, user_uuid=user_uuid,
        )
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
        existing = get_active_lock(db, user_uuid)
        raise LifecycleLocked(
            f"User lifecycle is already locked: {user_uuid}",
            operation=getattr(existing, "operation", None),
            job_id=getattr(existing, "job_id", None), user_uuid=user_uuid,
        ) from exc
    return row


def get_active_lock(db, user_uuid: str) -> UserLifecycleLock | None:
    return db.query(UserLifecycleLock).filter(UserLifecycleLock.user_uuid == user_uuid).first()


def release_lifecycle_lock(db, user_uuid: str, owner_token: str) -> bool:
    row = db.query(UserLifecycleLock).filter(UserLifecycleLock.user_uuid == user_uuid).first()
    if row is None:
        return False
    if row.owner_token != owner_token:
        raise LifecycleLocked(
            "Lifecycle lock owner token mismatch", operation=row.operation,
            job_id=row.job_id, user_uuid=user_uuid,
        )
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


@contextmanager
def transient_user_mutation_lock(db, user_uuid: str, operation: str, *, ttl_seconds: int = 120):
    now = int(time.time())
    existing = get_active_lock(db, user_uuid)
    if existing is not None and existing.job_id is None and existing.expires_at is not None and int(existing.expires_at) <= now:
        db.delete(existing)
        db.commit()
        existing = None
    if existing is not None:
        raise LifecycleLocked(
            f"User lifecycle is already locked: {user_uuid}",
            operation=existing.operation, job_id=existing.job_id, user_uuid=user_uuid,
        )
    lock = acquire_lifecycle_lock(
        db, user_uuid, operation, None, expires_at=now + max(30, int(ttl_seconds))
    )
    db.commit()
    token = lock.owner_token
    try:
        yield lock
    except Exception:
        db.rollback()
        raise
    finally:
        current = get_active_lock(db, user_uuid)
        if current is not None and current.owner_token == token and current.job_id is None:
            db.delete(current)
            db.commit()
