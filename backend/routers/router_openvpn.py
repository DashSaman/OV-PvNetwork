"""Panel control plane for the opt-in Router/OpenVPN listener."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user
from backend.db.engine import get_db
from backend.db.models import Node, NodeRouterOpenVpnConfig, RouterOpenVpnCredential
from backend.node.requests import NodeRequests

router = APIRouter(prefix="/router-openvpn", tags=["Router OpenVPN"])


class RouterOpenVpnConfigInput(BaseModel):
    enabled: bool = True
    port: int = Field(default=1195, ge=1, le=65535)
    protocol: str = "tcp"
    subnet: str = "10.9.0.0/24"

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, value: str) -> str:
        value = str(value).lower().strip()
        if value not in {"tcp", "udp"}:
            raise ValueError("protocol must be tcp or udp")
        return value


def _node(db: Session, node_id: int) -> Node:
    node = db.get(Node, int(node_id))
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


def _require_visible(actor: dict) -> None:
    if actor.get("type") not in {"admin", "main_admin"}:
        raise HTTPException(status_code=403, detail="Administrator access required")


def _require_main(actor: dict) -> None:
    if actor.get("type") != "main_admin":
        raise HTTPException(status_code=403, detail="Main administrator access is required")


def _client(node: Node) -> NodeRequests:
    return NodeRequests(
        address=node.address,
        port=node.port,
        api_key=node.key,
        tunnel_address=node.tunnel_address or node.address,
        protocol=node.protocol,
        ovpn_port=node.ovpn_port,
        set_new_setting=False,
    )


def _status_payload(
    node: Node,
    config: NodeRouterOpenVpnConfig | None,
    remote: dict,
) -> dict:
    data = remote.get("data") if isinstance(remote.get("data"), dict) else {}
    return {
        "node_id": int(node.id),
        "node_name": str(node.name),
        "configured": config is not None,
        "enabled": bool(config.enabled) if config else False,
        "port": int(config.port) if config else int(data.get("port") or 1195),
        "protocol": str(config.protocol) if config else str(data.get("protocol") or "tcp"),
        "subnet": str(config.subnet) if config else str(data.get("subnet") or "10.9.0.0/24"),
        "capable": bool(remote.get("capable")),
        "healthy": bool(data.get("healthy")) if remote.get("ok") else False,
        "upgrade_required": bool(remote.get("upgrade_required")),
        "capability_version": (
            str(data.get("version")) if data.get("version") is not None else None
        ),
        "last_verified_at": config.last_verified_at if config else None,
        "last_error": config.last_error if config else None,
    }


@router.get("/nodes/{node_id}")
async def get_node_router_openvpn(
    node_id: int,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    _require_visible(actor)
    node = _node(db, node_id)
    config = db.get(NodeRouterOpenVpnConfig, int(node_id))
    remote = _client(node).router_openvpn_status()
    return {
        "success": True,
        "data": _status_payload(node, config, remote),
    }


@router.post("/nodes/{node_id}/preflight")
async def preflight_node_router_openvpn(
    node_id: int,
    request: RouterOpenVpnConfigInput,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    _require_main(actor)
    node = _node(db, node_id)
    remote = _client(node).router_openvpn_preflight(
        request.port, request.protocol, request.subnet
    )
    if remote.get("upgrade_required"):
        raise HTTPException(
            status_code=426,
            detail="Node Router/OpenVPN capability upgrade is required",
        )
    if not remote.get("ok"):
        detail = "Router/OpenVPN preflight failed"
        data = remote.get("data")
        if isinstance(data, dict) and data.get("error"):
            detail = str(data["error"])[:300]
        elif remote.get("msg"):
            detail = str(remote["msg"])[:300]
        raise HTTPException(status_code=409, detail=detail)
    return {
        "success": True,
        "data": {
            "node_id": int(node.id),
            "ok": True,
            "port": request.port,
            "protocol": request.protocol,
            "subnet": request.subnet,
        },
    }


def _upsert_config(
    db: Session,
    node_id: int,
    request: RouterOpenVpnConfigInput,
    *,
    enabled: bool,
    version: str | None,
) -> NodeRouterOpenVpnConfig:
    row = db.get(NodeRouterOpenVpnConfig, int(node_id))
    if row is None:
        row = NodeRouterOpenVpnConfig(node_id=int(node_id))
        db.add(row)
    row.enabled = bool(enabled)
    row.port = int(request.port)
    row.protocol = str(request.protocol)
    row.subnet = str(request.subnet)
    row.capability_version = version
    row.last_verified_at = int(time.time())
    row.last_error = None
    return row


@router.put("/nodes/{node_id}")
async def configure_node_router_openvpn(
    node_id: int,
    request: RouterOpenVpnConfigInput,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    _require_main(actor)
    node = _node(db, node_id)
    client = _client(node)
    existing = db.get(NodeRouterOpenVpnConfig, int(node_id))

    if not request.enabled and existing is not None and not bool(existing.enabled):
        return {
            "success": True,
            "data": {
                "node_id": int(node.id),
                "enabled": False,
                "healthy": False,
                "idempotent": True,
            },
        }

    if request.enabled and existing is not None and bool(existing.enabled):
        same_settings = (
            int(existing.port) == int(request.port)
            and str(existing.protocol) == str(request.protocol)
            and str(existing.subnet) == str(request.subnet)
        )
        if same_settings:
            current = client.router_openvpn_status()
            current_data = (
                current.get("data")
                if isinstance(current.get("data"), dict)
                else {}
            )
            if current.get("ok") and current_data.get("enabled") and current_data.get("healthy"):
                return {
                    "success": True,
                    "data": {
                        "node_id": int(node.id),
                        "enabled": True,
                        "healthy": True,
                        "capable": True,
                        "upgrade_required": False,
                        "port": int(existing.port),
                        "protocol": str(existing.protocol),
                        "subnet": str(existing.subnet),
                        "capability_version": existing.capability_version,
                        "idempotent": True,
                    },
                }

    if not request.enabled:
        remote = client.router_openvpn_config(
            enabled=False,
            port=request.port,
            protocol=request.protocol,
            subnet=request.subnet,
        )
        if remote.get("upgrade_required"):
            raise HTTPException(
                status_code=426,
                detail="Node Router/OpenVPN capability upgrade is required",
            )
        if not remote.get("ok"):
            raise HTTPException(
                status_code=502,
                detail="Node failed to disable Router/OpenVPN listener",
            )
        _upsert_config(
            db,
            node_id,
            request,
            enabled=False,
            version=None,
        )
        db.query(RouterOpenVpnCredential).filter(
            RouterOpenVpnCredential.node_id == int(node_id)
        ).update(
            {RouterOpenVpnCredential.enabled: False},
            synchronize_session=False,
        )
        db.commit()
        return {
            "success": True,
            "data": {
                "node_id": int(node.id),
                "enabled": False,
                "healthy": False,
            },
        }

    preflight = client.router_openvpn_preflight(
        request.port,
        request.protocol,
        request.subnet,
    )
    if preflight.get("upgrade_required"):
        raise HTTPException(
            status_code=426,
            detail="Node Router/OpenVPN capability upgrade is required",
        )
    if not preflight.get("ok"):
        raise HTTPException(
            status_code=409,
            detail="Router/OpenVPN preflight failed",
        )

    configured = client.router_openvpn_config(
        enabled=True,
        port=request.port,
        protocol=request.protocol,
        subnet=request.subnet,
    )
    if not configured.get("ok"):
        raise HTTPException(
            status_code=502,
            detail="Node failed to enable Router/OpenVPN listener",
        )

    status = client.router_openvpn_status()
    status_data = status.get("data") if isinstance(status.get("data"), dict) else {}
    healthy = bool(
        status.get("ok")
        and status_data.get("enabled")
        and status_data.get("healthy")
    )
    if not healthy:
        db.rollback()
        try:
            client.router_openvpn_config(
                enabled=False,
                port=request.port,
                protocol=request.protocol,
                subnet=request.subnet,
            )
        finally:
            raise HTTPException(
                status_code=502,
                detail="Router/OpenVPN listener failed post-enable health verification",
            )
    row = _upsert_config(
        db,
        node_id,
        request,
        enabled=True,
        version=(
            str(status_data.get("version"))
            if status_data.get("version") is not None
            else None
        ),
    )
    db.commit()
    return {
        "success": True,
        "data": {
            "node_id": int(node.id),
            "enabled": bool(row.enabled),
            "healthy": True,
            "capable": True,
            "upgrade_required": False,
            "port": int(row.port),
            "protocol": str(row.protocol),
            "subnet": str(row.subnet),
            "capability_version": row.capability_version,
        },
    }
