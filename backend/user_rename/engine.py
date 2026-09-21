from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict

from backend.db.models import ActiveSession, Node, User, UserRenameJob
from backend.node.assignment import _node_request, snapshot_assigned_nodes
from backend.user_rename.contracts import RenameState, TERMINAL_RENAME_STATES
from backend.user_rename.repository import (
    LifecycleLocked, acquire_lifecycle_lock, get_active_lock,
    get_rename_job, release_lifecycle_lock,
)


class RenameStageError(RuntimeError):
    pass


def _load_json(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _save(job, db, *, state: str | None = None, snapshot: dict | None = None, evidence: dict | None = None, failure: str | None = None) -> None:
    if state is not None:
        job.state = state
    if snapshot is not None:
        job.snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    if evidence is not None:
        job.evidence_json = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    job.failure_reason = failure
    job.updated_at = int(time.time())
    db.commit()
    db.refresh(job)


def _node_by_id(db, node_id: int) -> Node:
    node = db.query(Node).filter(Node.id == int(node_id)).first()
    if node is None:
        raise RenameStageError(f"Assigned node missing: {node_id}")
    return node


def _cn(username: str, node_name: str) -> str:
    return f"{username}-{node_name}"


async def preflight_job(job, db) -> dict:
    user = db.query(User).filter(User.uuid == job.user_uuid).first()
    if user is None or user.name != job.old_name:
        raise RenameStageError("User identity changed before rename preflight")
    collision = db.query(User).filter(User.name == job.new_name, User.uuid != job.user_uuid).first()
    if collision is not None:
        raise RenameStageError("Target username already exists")
    assigned = snapshot_assigned_nodes(db, job.user_uuid)
    if not assigned:
        raise RenameStageError("User has no assigned nodes")
    snapshot = {
        "user_uuid": user.uuid,
        "old_name": job.old_name,
        "new_name": job.new_name,
        "original_active": bool(user.is_active),
        "owner": user.owner,
        "total": int(user.total or 0),
        "used": int(user.used or 0),
        "expiry_date": user.expiry_date.isoformat(),
        "device_limit": int(user.device_limit or 0),
        "node_ids": [x.id for x in assigned],
        "nodes": [asdict(x) for x in assigned],
    }
    evidence = _load_json(job.evidence_json)
    evidence.setdefault("staged_node_ids", [])
    evidence.setdefault("disabled_old_node_ids", [])
    evidence.setdefault("revoked_old_node_ids", [])
    evidence.setdefault("nodes", [])
    for item in assigned:
        node = _node_by_id(db, item.id)
        if not node.status or getattr(node, "drain", False) or getattr(node, "maintenance", False):
            raise RenameStageError(f"Assigned node unavailable: {node.id}")
        request = _node_request(node)
        if not await asyncio.to_thread(request.check_node):
            raise RenameStageError(f"Assigned node unreachable: {node.id}")
        new_state = await asyncio.to_thread(request.get_user_identity, _cn(job.new_name, node.name))
        if not new_state or new_state.get("capability_version") != "pvn-user-identity-v1":
            raise RenameStageError(f"Node identity capability unavailable: {node.id}")
        if new_state.get("exists"):
            raise RenameStageError(f"Target identity already exists on node: {node.id}")
    _save(job, db, state=RenameState.PREFLIGHT.value, snapshot=snapshot, evidence=evidence)
    return snapshot


async def _cleanup_staged(job, db, node_ids: list[int]) -> list[int]:
    failed: list[int] = []
    for node_id in node_ids:
        node = _node_by_id(db, node_id)
        request = _node_request(node)
        ok = await asyncio.to_thread(request.delete_user, _cn(job.new_name, node.name))
        if not ok:
            failed.append(node_id)
    return failed


async def stage_new_identities(job, db) -> dict:
    snapshot = _load_json(job.snapshot_json)
    if not snapshot.get("node_ids"):
        snapshot = await preflight_job(job, db)
    evidence = _load_json(job.evidence_json)
    staged = [int(x) for x in evidence.get("staged_node_ids", [])]
    _save(job, db, state=RenameState.STAGING.value, evidence=evidence)
    try:
        for node_id in snapshot["node_ids"]:
            node_id = int(node_id)
            if node_id in staged:
                continue
            node = _node_by_id(db, node_id)
            request = _node_request(node)
            new_cn = _cn(job.new_name, node.name)
            if not await asyncio.to_thread(request.create_user, new_cn):
                raise RenameStageError(f"Could not create staged identity on node {node_id}")
            staged.append(node_id)
            evidence["staged_node_ids"] = staged
            _save(job, db, state=RenameState.STAGING.value, evidence=evidence)
            state = await asyncio.to_thread(request.get_user_identity, new_cn)
            profile = await asyncio.to_thread(request.download_ovpn_client, new_cn)
            if not state or not state.get("exists") or not state.get("valid_certificate") or profile is None:
                raise RenameStageError(f"Staged identity verification failed on node {node_id}")
            if not snapshot.get("original_active", True):
                if not await asyncio.to_thread(request.change_user_status, new_cn, False):
                    raise RenameStageError(f"Could not preserve inactive state on node {node_id}")
        return evidence
    except Exception as exc:
        failed = await _cleanup_staged(job, db, list(staged))
        evidence["staged_node_ids"] = staged
        evidence["rollback_failed_node_ids"] = failed
        state = RenameState.ROLLED_BACK.value if not failed else RenameState.FAILED.value
        _save(job, db, state=state, evidence=evidence, failure=str(exc)[:500])
        if isinstance(exc, RenameStageError):
            raise
        raise RenameStageError(str(exc)) from exc


async def rollback_precommit(job, db) -> bool:
    snapshot = _load_json(job.snapshot_json)
    evidence = _load_json(job.evidence_json)
    failed: list[int] = []
    disabled = [int(x) for x in evidence.get("disabled_old_node_ids", [])]
    staged = [int(x) for x in evidence.get("staged_node_ids", [])]
    if snapshot.get("original_active", True):
        for node_id in disabled:
            node = _node_by_id(db, node_id)
            if not await asyncio.to_thread(_node_request(node).change_user_status, _cn(job.old_name, node.name), True):
                failed.append(node_id)
    for node_id in staged:
        node = _node_by_id(db, node_id)
        if not await asyncio.to_thread(_node_request(node).delete_user, _cn(job.new_name, node.name)):
            failed.append(node_id)
    evidence["rollback_failed_node_ids"] = sorted(set(failed))
    state = RenameState.ROLLED_BACK.value if not failed else RenameState.FAILED.value
    _save(job, db, state=state, evidence=evidence, failure=None if not failed else "Pre-commit compensation incomplete")
    return not failed


async def disable_old_identities(job, db) -> dict:
    snapshot = _load_json(job.snapshot_json)
    evidence = _load_json(job.evidence_json)
    disabled = [int(x) for x in evidence.get("disabled_old_node_ids", [])]
    try:
        for node_id in snapshot.get("node_ids", []):
            node_id = int(node_id)
            if node_id in disabled:
                continue
            node = _node_by_id(db, node_id)
            request = _node_request(node)
            old_cn = _cn(job.old_name, node.name)
            if not await asyncio.to_thread(request.change_user_status, old_cn, False):
                raise RenameStageError(f"Could not disable old identity on node {node_id}")
            state = await asyncio.to_thread(request.get_user_identity, old_cn)
            if not state or state.get("connected"):
                raise RenameStageError(f"Old identity still connected on node {node_id}")
            disabled.append(node_id)
            evidence["disabled_old_node_ids"] = disabled
            _save(job, db, state=RenameState.CUTOVER.value, evidence=evidence)
        return evidence
    except Exception as exc:
        await rollback_precommit(job, db)
        if isinstance(exc, RenameStageError):
            raise
        raise RenameStageError(str(exc)) from exc


async def revoke_old_identities(job, db) -> tuple[bool, list[int]]:
    snapshot = _load_json(job.snapshot_json)
    evidence = _load_json(job.evidence_json)
    revoked = [int(x) for x in evidence.get("revoked_old_node_ids", [])]
    failed: list[int] = []
    for node_id in snapshot.get("node_ids", []):
        node_id = int(node_id)
        if node_id in revoked:
            continue
        node = _node_by_id(db, node_id)
        request = _node_request(node)
        old_cn = _cn(job.old_name, node.name)
        ok = await asyncio.to_thread(request.delete_user, old_cn)
        state = await asyncio.to_thread(request.get_user_identity, old_cn) if ok else {}
        verified = bool(ok and state and not state.get("valid_certificate") and not state.get("profile_exists") and not state.get("connected"))
        if verified:
            revoked.append(node_id)
            evidence["revoked_old_node_ids"] = revoked
            _save(job, db, evidence=evidence)
        else:
            failed.append(node_id)
    evidence["cleanup_failed_node_ids"] = sorted(failed)
    _save(job, db, evidence=evidence)
    return not failed, failed


def commit_central_rename(job_id: str, db) -> None:
    job = db.query(UserRenameJob).filter(UserRenameJob.id == job_id).with_for_update().first()
    if job is None:
        raise RenameStageError("Rename job not found")
    user = db.query(User).filter(User.uuid == job.user_uuid).with_for_update().first()
    if user is None:
        raise RenameStageError("User not found during rename cutover")
    if user.name == job.new_name:
        if job.state not in {RenameState.REVOKING_OLD.value, RenameState.CLEANUP_PENDING.value, RenameState.COMPLETED.value}:
            job.state = RenameState.REVOKING_OLD.value
            job.updated_at = int(time.time())
            db.commit()
        return
    if user.name != job.old_name:
        raise RenameStageError("Central username changed outside rename job")
    collision = db.query(User).filter(User.name == job.new_name, User.uuid != job.user_uuid).first()
    if collision is not None:
        raise RenameStageError("Target username already exists")
    snapshot = _load_json(job.snapshot_json)
    old_cns = [_cn(job.old_name, str(item.get("name"))) for item in snapshot.get("nodes", []) if isinstance(item, dict) and item.get("name")]
    if old_cns:
        db.query(ActiveSession).filter(
            ActiveSession.user_uuid == job.user_uuid,
            ActiveSession.common_name.in_(old_cns),
        ).delete(synchronize_session=False)
    now = int(time.time())
    user.name = job.new_name
    evidence = _load_json(job.evidence_json)
    evidence["audit"] = {
        "old_name": job.old_name, "new_name": job.new_name,
        "actor": job.actor, "actor_type": job.actor_type, "job_id": job.id,
        "cutover_at": now,
    }
    job.evidence_json = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    job.state = RenameState.REVOKING_OLD.value
    job.updated_at = now
    job.failure_reason = None
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _ensure_job_lock(job, db):
    lock = get_active_lock(db, job.user_uuid)
    if lock is None:
        lock = acquire_lifecycle_lock(db, job.user_uuid, "rename", job.id)
        db.commit()
    elif lock.operation != "rename" or lock.job_id not in {None, job.id}:
        raise LifecycleLocked(f"Conflicting lifecycle lock for {job.user_uuid}")
    return lock


def _complete_job(job, db) -> str:
    now = int(time.time())
    evidence = _load_json(job.evidence_json)
    audit = evidence.setdefault("audit", {})
    audit["terminal_at"] = now
    job.evidence_json = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    job.state = RenameState.COMPLETED.value
    job.completed_at = now
    job.updated_at = now
    job.failure_reason = None
    lock = get_active_lock(db, job.user_uuid)
    if lock is not None and lock.operation == "rename" and lock.job_id in {None, job.id}:
        release_lifecycle_lock(db, job.user_uuid, lock.owner_token)
    db.commit()
    return job.state


async def _attempt_cleanup(job, db) -> str:
    ok, failed = await revoke_old_identities(job, db)
    if not ok:
        evidence = _load_json(job.evidence_json)
        evidence["cleanup_failed_node_ids"] = sorted(set(int(x) for x in failed))
        _save(job, db, state=RenameState.CLEANUP_PENDING.value, evidence=evidence, failure="Old identity cleanup pending")
        return job.state
    return _complete_job(job, db)


async def retry_cleanup(job_id: str, db=None) -> str:
    if db is None:
        from backend.db.engine import db_session
        with db_session() as session:
            return await retry_cleanup(job_id, session)
    job = get_rename_job(db, job_id)
    if job is None:
        raise RenameStageError("Rename job not found")
    if job.state != RenameState.CLEANUP_PENDING.value:
        raise RenameStageError("Cleanup retry is allowed only for cleanup_pending jobs")
    _ensure_job_lock(job, db)
    return await _attempt_cleanup(job, db)


async def run_rename_job(job_id: str, db=None) -> str:
    if db is None:
        from backend.db.engine import db_session
        with db_session() as session:
            return await run_rename_job(job_id, session)
    job = get_rename_job(db, job_id)
    if job is None:
        raise RenameStageError("Rename job not found")
    if job.state in TERMINAL_RENAME_STATES:
        return job.state
    _ensure_job_lock(job, db)
    try:
        while True:
            db.refresh(job)
            if job.state in TERMINAL_RENAME_STATES:
                lock = get_active_lock(db, job.user_uuid)
                if lock is not None and lock.operation == "rename" and lock.job_id in {None, job.id}:
                    release_lifecycle_lock(db, job.user_uuid, lock.owner_token); db.commit()
                return job.state
            if job.state == RenameState.QUEUED.value:
                await preflight_job(job, db); continue
            if job.state == RenameState.PREFLIGHT.value:
                await stage_new_identities(job, db); continue
            if job.state == RenameState.STAGING.value:
                await stage_new_identities(job, db)
                await disable_old_identities(job, db); continue
            if job.state == RenameState.ROLLING_BACK.value:
                await rollback_precommit(job, db); continue
            if job.state == RenameState.CUTOVER.value:
                commit_central_rename(job.id, db); continue
            if job.state == RenameState.REVOKING_OLD.value:
                return await _attempt_cleanup(job, db)
            if job.state == RenameState.CLEANUP_PENDING.value:
                return job.state
            raise RenameStageError(f"Unsupported rename state: {job.state}")
    except RenameStageError:
        db.refresh(job)
        if job.state in {RenameState.ROLLED_BACK.value, RenameState.FAILED.value}:
            lock = get_active_lock(db, job.user_uuid)
            if lock is not None and lock.operation == "rename" and lock.job_id in {None, job.id}:
                release_lifecycle_lock(db, job.user_uuid, lock.owner_token); db.commit()
        raise
