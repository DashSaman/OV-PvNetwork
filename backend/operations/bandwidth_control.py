"""Emergency OpenVPN bandwidth policy planning and node reconciliation.

The panel stores only policy intent. Every node receives a short renewable lease.
If the panel or reconciliation timer stops, node-side shaping automatically expires
and the previous qdisc is restored (fail-open).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy.orm import Session

from backend.db.engine import SessionLocal
from backend.db.models import (
    BandwidthSettings,
    Node,
    User,
    UserBandwidthGroup,
    UserNode,
)
from backend.node.requests import NodeRequests


LEASE_SECONDS = 180
VALID_TARGET_TYPES = {"all", "owner", "group", "users"}


@dataclass(frozen=True)
class PolicySpec:
    target_type: str
    download_kbit: int
    node_ids: list[int]
    group_id: int | None = None
    owner: str | None = None
    user_uuids: list[str] | None = None
    expires_at: int | None = None
    revision: int = 0


def _json_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


def ensure_settings(db: Session) -> BandwidthSettings:
    row = db.query(BandwidthSettings).filter(BandwidthSettings.id == 1).first()
    if row is None:
        row = BandwidthSettings(
            id=1,
            enabled=False,
            target_type="all",
            target_user_uuids="[]",
            node_ids="[]",
            download_kbit=1000,
            revision=0,
            updated_at=0,
        )
        db.add(row)
        db.flush()
    return row


def spec_from_settings(row: BandwidthSettings) -> PolicySpec:
    return PolicySpec(
        target_type=str(row.target_type or "all"),
        download_kbit=int(row.download_kbit or 1000),
        node_ids=[int(value) for value in _json_list(row.node_ids)],
        group_id=(int(row.target_group_id) if row.target_group_id is not None else None),
        owner=(str(row.target_owner) if row.target_owner else None),
        user_uuids=[str(value) for value in _json_list(row.target_user_uuids)],
        expires_at=(int(row.expires_at) if row.expires_at is not None else None),
        revision=int(row.revision or 0),
    )


def node_client(node: Node) -> NodeRequests:
    return NodeRequests(
        address=str(node.address),
        port=int(node.port),
        api_key=str(node.key),
        tunnel_address=str(node.tunnel_address or node.address),
        protocol=str(node.protocol),
        ovpn_port=int(node.ovpn_port),
        set_new_setting=False,
    )


def _query_users_for_node(db: Session, node_id: int):
    return (
        db.query(User)
        .join(UserNode, UserNode.user_uuid == User.uuid)
        .filter(UserNode.node_id == node_id)
    )


def _resolved_users(db: Session, node: Node, spec: PolicySpec) -> list[User]:
    query = _query_users_for_node(db, int(node.id))

    if spec.target_type == "all":
        return query.order_by(User.id).all()

    if spec.target_type == "owner":
        query = query.filter(User.owner == str(spec.owner or ""))

    elif spec.target_type == "group":
        query = query.join(
            UserBandwidthGroup,
            UserBandwidthGroup.user_uuid == User.uuid,
        ).filter(UserBandwidthGroup.group_id == int(spec.group_id or 0))

    elif spec.target_type == "users":
        uuids = [str(value) for value in (spec.user_uuids or [])]
        if not uuids:
            return []
        query = query.filter(User.uuid.in_(uuids))

    else:
        return []

    return query.order_by(User.id).all()


def build_node_plans(
    db: Session,
    spec: PolicySpec,
    *,
    lease_seconds: int = LEASE_SECONDS,
    now: int | None = None,
) -> list[dict[str, Any]]:
    if spec.target_type not in VALID_TARGET_TYPES:
        raise ValueError("Invalid bandwidth target type")
    if not spec.node_ids:
        raise ValueError("At least one node is required")
    if not 64 <= int(spec.download_kbit) <= 10_000_000:
        raise ValueError("Download rate is outside the allowed range")

    current_time = int(now or time.time())
    nodes = (
        db.query(Node)
        .filter(Node.id.in_([int(value) for value in spec.node_ids]))
        .order_by(Node.id)
        .all()
    )
    found_ids = {int(node.id) for node in nodes}
    missing = [int(value) for value in spec.node_ids if int(value) not in found_ids]
    if missing:
        raise ValueError(f"Unknown node IDs: {missing}")

    plans: list[dict[str, Any]] = []
    for node in nodes:
        users = _resolved_users(db, node, spec)
        targets = [f"{item.name}-{node.name}" for item in users]
        scope = "all" if spec.target_type == "all" else "targets"
        payload = {
            "enabled": True,
            "revision": int(spec.revision),
            "scope": scope,
            "targets": targets,
            "rate_kbit": int(spec.download_kbit),
            "expires_at": spec.expires_at,
            "lease_expires_at": current_time + int(lease_seconds),
            "interface": "tun0",
        }
        plans.append(
            {
                "node_id": int(node.id),
                "node_name": str(node.name),
                "address": str(node.address),
                "port": int(node.port),
                "api_key": str(node.key),
                "tunnel_address": str(node.tunnel_address or node.address),
                "protocol": str(node.protocol),
                "ovpn_port": int(node.ovpn_port),
                "payload": payload,
                "configured_users": len(users),
            }
        )
    return plans


def client_from_plan(plan: dict[str, Any]) -> NodeRequests:
    return NodeRequests(
        address=plan["address"],
        port=int(plan["port"]),
        api_key=plan["api_key"],
        tunnel_address=plan["tunnel_address"],
        protocol=plan["protocol"],
        ovpn_port=int(plan["ovpn_port"]),
        set_new_setting=False,
    )


def apply_plans(plans: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for plan in plans:
        response = client_from_plan(plan).bandwidth_apply(plan["payload"])
        results.append(
            {
                "node_id": plan["node_id"],
                "node_name": plan["node_name"],
                "configured_users": plan["configured_users"],
                **response,
            }
        )
    return results


def disable_nodes(nodes: Iterable[Node], *, revision: int = 0) -> list[dict[str, Any]]:
    results = []
    for node in nodes:
        response = node_client(node).bandwidth_disable(
            {"revision": int(revision)}
        )
        results.append(
            {
                "node_id": int(node.id),
                "node_name": str(node.name),
                **response,
            }
        )
    return results


def reconcile_persisted_settings() -> dict[str, Any]:
    """Refresh short node leases for the currently active policy."""
    db = SessionLocal()
    try:
        row = ensure_settings(db)
        now = int(time.time())

        if not bool(row.enabled):
            db.rollback()
            return {"enabled": False, "results": []}

        if row.expires_at is not None and int(row.expires_at) <= now:
            row.enabled = False
            row.revision = max(int(row.revision or 0) + 1, now * 1000)
            row.updated_at = now
            revision = int(row.revision)
            nodes = list(db.query(Node).all())
            db.commit()
            return {
                "enabled": False,
                "expired": True,
                "results": disable_nodes(nodes, revision=revision),
            }

        spec = spec_from_settings(row)
        plans = build_node_plans(db, spec, now=now)
        db.rollback()
    finally:
        db.close()

    return {
        "enabled": True,
        "results": apply_plans(plans),
    }
