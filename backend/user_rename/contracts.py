from __future__ import annotations

import json
import re
from enum import Enum

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


class RenameState(str, Enum):
    QUEUED = "queued"
    PREFLIGHT = "preflight"
    STAGING = "staging"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    CUTOVER = "cutover"
    REVOKING_OLD = "revoking_old"
    CLEANUP_PENDING = "cleanup_pending"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_RENAME_STATES = {
    RenameState.ROLLED_BACK.value,
    RenameState.COMPLETED.value,
    RenameState.FAILED.value,
}


def normalize_rename_username(value: str) -> str:
    candidate = str(value or "").strip()
    if not _USERNAME_RE.fullmatch(candidate):
        raise ValueError("Username must be 3-64 characters using only letters, numbers, _ or -")
    return candidate


def _json_object(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def serialize_rename_job(job) -> dict:
    snapshot = _json_object(getattr(job, "snapshot_json", None))
    evidence = _json_object(getattr(job, "evidence_json", None))
    safe_nodes = []
    for item in evidence.get("nodes", []):
        if not isinstance(item, dict):
            continue
        safe_nodes.append({
            key: item[key]
            for key in ("node_id", "name", "stage", "status", "error")
            if key in item
        })
    return {
        "id": job.id,
        "user_uuid": job.user_uuid,
        "old_name": job.old_name,
        "new_name": job.new_name,
        "state": job.state,
        "actor": job.actor,
        "actor_type": job.actor_type,
        "node_ids": [int(x) for x in snapshot.get("node_ids", []) if isinstance(x, int) or str(x).isdigit()],
        "nodes": safe_nodes,
        "failure_reason": getattr(job, "failure_reason", None),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "completed_at": getattr(job, "completed_at", None),
    }
