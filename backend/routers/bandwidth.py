from __future__ import annotations

import asyncio
import json
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user
from backend.db.engine import get_db
from backend.db.models import (
    BandwidthGroup,
    BandwidthSettings,
    Node,
    User,
    UserBandwidthGroup,
    UserNode,
)
from backend.operations.bandwidth_control import (
    LEASE_SECONDS,
    PolicySpec,
    build_node_plans,
    client_from_plan,
    disable_nodes,
    ensure_settings,
    node_client,
)
from backend.schema.output import ResponseModel


router = APIRouter(prefix="/bandwidth", tags=["Bandwidth Control"])


def _main_admin(user: dict) -> None:
    if user.get("type") != "main_admin":
        raise HTTPException(status_code=403, detail="Main administrator required")


def _safe_json_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class GroupMembers(BaseModel):
    user_uuids: list[str] = Field(default_factory=list, max_length=10000)


class PolicyRequest(BaseModel):
    target_type: Literal["all", "owner", "group", "users"] = "all"
    download_mbps: float = Field(default=1.0, ge=0.064, le=10000)
    node_ids: list[int] = Field(min_length=1, max_length=256)
    group_id: int | None = None
    owner: str | None = Field(default=None, max_length=128)
    user_uuids: list[str] = Field(default_factory=list, max_length=10000)
    duration_minutes: int | None = Field(default=0, ge=0, le=10080)
    canary_node_id: int | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_type == "owner" and not (self.owner or "").strip():
            raise ValueError("Owner is required")
        if self.target_type == "group" and not self.group_id:
            raise ValueError("Bandwidth group is required")
        if self.target_type == "users" and not self.user_uuids:
            raise ValueError("At least one user is required")
        if self.canary_node_id is not None and self.canary_node_id not in self.node_ids:
            raise ValueError("Canary node must be one of the selected nodes")
        return self


class ActivateRequest(PolicyRequest):
    confirmation: str = Field(min_length=5, max_length=16)
    canary_only: bool = False


class DisableRequest(BaseModel):
    confirmation: str = Field(default="DISABLE", min_length=7, max_length=16)


def _settings_payload(row: BandwidthSettings) -> dict:
    return {
        "enabled": bool(row.enabled),
        "target_type": str(row.target_type or "all"),
        "target_group_id": row.target_group_id,
        "target_owner": row.target_owner,
        "target_user_uuids": [str(x) for x in _safe_json_list(row.target_user_uuids)],
        "node_ids": [int(x) for x in _safe_json_list(row.node_ids)],
        "download_mbps": round(int(row.download_kbit or 1000) / 1000, 3),
        "download_kbit": int(row.download_kbit or 1000),
        "expires_at": row.expires_at,
        "revision": int(row.revision or 0),
        "updated_at": int(row.updated_at or 0),
        "updated_by": row.updated_by,
    }


def _request_to_spec(request: PolicyRequest, *, revision: int, node_ids: list[int] | None = None) -> PolicySpec:
    now = int(time.time())
    duration = int(request.duration_minutes or 0)
    expires_at = now + duration * 60 if duration > 0 else None
    return PolicySpec(
        target_type=request.target_type,
        download_kbit=max(64, int(round(float(request.download_mbps) * 1000))),
        node_ids=[int(x) for x in (node_ids or request.node_ids)],
        group_id=request.group_id,
        owner=(request.owner or "").strip() or None,
        user_uuids=[str(x) for x in request.user_uuids],
        expires_at=expires_at,
        revision=int(revision),
    )


def _validate_references(db: Session, request: PolicyRequest) -> None:
    nodes = db.query(Node.id).filter(Node.id.in_(request.node_ids)).all()
    found_nodes = {int(value) for (value,) in nodes}
    missing_nodes = [int(value) for value in request.node_ids if int(value) not in found_nodes]
    if missing_nodes:
        raise HTTPException(status_code=422, detail=f"Unknown node IDs: {missing_nodes}")

    if request.target_type == "group":
        group = db.query(BandwidthGroup).filter(BandwidthGroup.id == request.group_id).first()
        if group is None:
            raise HTTPException(status_code=422, detail="Bandwidth group not found")

    if request.target_type == "owner":
        exists = db.query(User.id).filter(User.owner == request.owner).first()
        if exists is None:
            raise HTTPException(status_code=422, detail="Owner has no users")

    if request.target_type == "users":
        found = {
            value
            for (value,) in db.query(User.uuid)
            .filter(User.uuid.in_(request.user_uuids))
            .all()
        }
        missing = [value for value in request.user_uuids if value not in found]
        if missing:
            raise HTTPException(status_code=422, detail=f"Unknown user UUIDs: {missing[:20]}")


def _group_rows(db: Session) -> list[dict]:
    counts = dict(
        db.query(
            UserBandwidthGroup.group_id,
            func.count(UserBandwidthGroup.user_uuid),
        )
        .group_by(UserBandwidthGroup.group_id)
        .all()
    )
    rows = db.query(BandwidthGroup).order_by(BandwidthGroup.name).all()
    return [
        {
            "id": int(row.id),
            "name": row.name,
            "members_count": int(counts.get(row.id, 0)),
            "created_at": int(row.created_at),
            "updated_at": int(row.updated_at),
        }
        for row in rows
    ]


@router.get("/", response_model=ResponseModel)
async def get_configuration(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin(user)
    settings = ensure_settings(db)
    now = int(time.time())
    if settings.enabled and settings.expires_at is not None and int(settings.expires_at) <= now:
        settings.enabled = False
        settings.updated_at = now
        db.commit()

    group_map = {
        str(user_uuid): int(group_id)
        for user_uuid, group_id in db.query(
            UserBandwidthGroup.user_uuid,
            UserBandwidthGroup.group_id,
        ).all()
    }
    users = db.query(User).order_by(User.id.desc()).all()
    nodes = db.query(Node).order_by(Node.id).all()
    owners = [
        str(value)
        for (value,) in db.query(User.owner).distinct().order_by(User.owner).all()
    ]
    return ResponseModel(
        success=True,
        msg="Bandwidth control configuration",
        data={
            "settings": _settings_payload(settings),
            "groups": _group_rows(db),
            "owners": owners,
            "users": [
                {
                    "uuid": row.uuid,
                    "name": row.name,
                    "owner": row.owner,
                    "is_active": bool(row.is_active),
                    "group_id": group_map.get(str(row.uuid)),
                }
                for row in users
            ],
            "nodes": [
                {
                    "id": int(row.id),
                    "name": row.name,
                    "enabled": bool(row.status),
                }
                for row in nodes
            ],
            "safety": {
                "default_enabled": False,
                "download_only": True,
                "interface": "tun0",
                "lease_seconds": LEASE_SECONDS,
                "fail_open": True,
            },
        },
    )


@router.get("/status", response_model=ResponseModel)
async def get_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin(user)
    nodes = list(db.query(Node).order_by(Node.id).all())
    db.rollback()

    async def one(node: Node):
        result = await asyncio.to_thread(node_client(node).bandwidth_status)
        return {"node_id": int(node.id), "node_name": str(node.name), **result}

    results = await asyncio.gather(*(one(node) for node in nodes))
    return ResponseModel(success=True, msg="Bandwidth node status", data=results)


@router.post("/groups", response_model=ResponseModel)
async def create_group(
    request: GroupCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin(user)
    name = request.name.strip()
    duplicate = db.query(BandwidthGroup).filter(func.lower(BandwidthGroup.name) == name.lower()).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="A group with this name already exists")
    now = int(time.time())
    row = BandwidthGroup(name=name, created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ResponseModel(success=True, msg="Bandwidth group created", data={"id": row.id, "name": row.name})


@router.delete("/groups/{group_id}", response_model=ResponseModel)
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin(user)
    group = db.query(BandwidthGroup).filter(BandwidthGroup.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Bandwidth group not found")
    settings = ensure_settings(db)
    if settings.enabled and settings.target_type == "group" and settings.target_group_id == group_id:
        raise HTTPException(status_code=409, detail="Disable the active policy before deleting its group")
    db.delete(group)
    db.commit()
    return ResponseModel(success=True, msg="Bandwidth group deleted", data=None)


@router.put("/groups/{group_id}/users", response_model=ResponseModel)
async def replace_group_members(
    group_id: int,
    request: GroupMembers,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin(user)
    group = db.query(BandwidthGroup).filter(BandwidthGroup.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Bandwidth group not found")
    uuids = list(dict.fromkeys(str(value) for value in request.user_uuids))
    if uuids:
        found = {
            value
            for (value,) in db.query(User.uuid).filter(User.uuid.in_(uuids)).all()
        }
        missing = [value for value in uuids if value not in found]
        if missing:
            raise HTTPException(status_code=422, detail=f"Unknown user UUIDs: {missing[:20]}")
    now = int(time.time())
    db.query(UserBandwidthGroup).filter(UserBandwidthGroup.group_id == group_id).delete(synchronize_session=False)
    if uuids:
        db.query(UserBandwidthGroup).filter(UserBandwidthGroup.user_uuid.in_(uuids)).delete(synchronize_session=False)
        for uuid in uuids:
            db.add(UserBandwidthGroup(user_uuid=uuid, group_id=group_id, created_at=now))
    group.updated_at = now
    db.commit()
    return ResponseModel(success=True, msg="Bandwidth group members updated", data={"members_count": len(uuids)})


@router.post("/preview", response_model=ResponseModel)
async def preview_policy(
    request: PolicyRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin(user)
    _validate_references(db, request)
    current = ensure_settings(db)
    revision = max(int(current.revision or 0) + 1, int(time.time() * 1000))
    spec = _request_to_spec(request, revision=revision)
    plans = build_node_plans(db, spec)
    db.rollback()

    async def one(plan: dict):
        response = await asyncio.to_thread(client_from_plan(plan).bandwidth_preview, plan["payload"])
        return {
            "node_id": plan["node_id"],
            "node_name": plan["node_name"],
            "configured_users": plan["configured_users"],
            **response,
        }

    results = await asyncio.gather(*(one(plan) for plan in plans))
    return ResponseModel(
        success=all(item.get("ok") for item in results),
        msg="Bandwidth policy preview",
        data={
            "download_mbps": request.download_mbps,
            "target_type": request.target_type,
            "expires_at": spec.expires_at,
            "results": results,
        },
    )


@router.post("/activate", response_model=ResponseModel)
async def activate_policy(
    request: ActivateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin(user)
    if request.confirmation.strip().upper() != "APPLY":
        raise HTTPException(status_code=422, detail="Type APPLY to activate the policy")
    _validate_references(db, request)
    settings = ensure_settings(db)
    revision = max(int(settings.revision or 0) + 1, int(time.time() * 1000))

    selected_node_ids = list(request.node_ids)
    if request.canary_only:
        if request.canary_node_id is None:
            raise HTTPException(status_code=422, detail="Select a canary node")
        selected_node_ids = [int(request.canary_node_id)]

    spec = _request_to_spec(request, revision=revision, node_ids=selected_node_ids)
    plans = build_node_plans(db, spec)
    if request.canary_node_id is not None:
        plans.sort(key=lambda item: 0 if item["node_id"] == request.canary_node_id else 1)
    db.rollback()

    applied: list[dict] = []
    results: list[dict] = []
    for plan in plans:
        response = await asyncio.to_thread(client_from_plan(plan).bandwidth_apply, plan["payload"])
        item = {
            "node_id": plan["node_id"],
            "node_name": plan["node_name"],
            "configured_users": plan["configured_users"],
            **response,
        }
        results.append(item)
        if not item.get("ok"):
            for prior in applied:
                await asyncio.to_thread(
                    client_from_plan(prior).bandwidth_disable,
                    {"revision": revision},
                )
            return ResponseModel(
                success=False,
                msg="Activation failed; already-applied nodes were rolled back",
                data={"results": results},
            )
        applied.append(plan)

    try:
        settings = ensure_settings(db)
        settings.enabled = True
        settings.target_type = spec.target_type
        settings.target_group_id = spec.group_id
        settings.target_owner = spec.owner
        settings.target_user_uuids = json.dumps(spec.user_uuids or [])
        settings.node_ids = json.dumps(spec.node_ids)
        settings.download_kbit = spec.download_kbit
        settings.expires_at = spec.expires_at
        settings.revision = revision
        settings.updated_at = int(time.time())
        settings.updated_by = str(user.get("username") or "main_admin")
        db.commit()
    except Exception:
        db.rollback()
        for prior in applied:
            await asyncio.to_thread(
                client_from_plan(prior).bandwidth_disable,
                {"revision": revision},
            )
        raise

    return ResponseModel(
        success=True,
        msg="Emergency bandwidth policy activated",
        data={"settings": _settings_payload(settings), "results": results},
    )


@router.post("/disable", response_model=ResponseModel)
async def disable_policy(
    request: DisableRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin(user)
    if request.confirmation.strip().upper() != "DISABLE":
        raise HTTPException(status_code=422, detail="Invalid disable confirmation")
    settings = ensure_settings(db)
    revision = max(int(settings.revision or 0) + 1, int(time.time() * 1000))
    settings.enabled = False
    settings.expires_at = None
    settings.revision = revision
    settings.updated_at = int(time.time())
    settings.updated_by = str(user.get("username") or "main_admin")
    nodes = list(db.query(Node).order_by(Node.id).all())
    db.commit()
    results = await asyncio.to_thread(disable_nodes, nodes, revision=revision)
    return ResponseModel(
        success=True,
        msg="Emergency bandwidth policy disabled",
        data={
            "settings": _settings_payload(settings),
            "results": results,
            "note": "Unreachable nodes automatically fail open when their short lease expires.",
        },
    )
