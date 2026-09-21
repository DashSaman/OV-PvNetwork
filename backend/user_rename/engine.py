from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict

from backend.db.models import Node, User
from backend.node.assignment import _node_request, snapshot_assigned_nodes
from backend.user_rename.contracts import RenameState


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
        ok = await asyncio.to_thread(_node_request(node).delete_user, _cn(job.old_name, node.name))
        if ok:
            revoked.append(node_id)
            evidence["revoked_old_node_ids"] = revoked
            _save(job, db, evidence=evidence)
        else:
            failed.append(node_id)
    return not failed, failed
