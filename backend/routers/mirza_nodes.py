from __future__ import annotations

import secrets
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.config import config
from backend.db.engine import get_db
from backend.db.models import Node, UserNode
from backend.node.requests import NodeRequests


router = APIRouter(
    prefix="/integrations/mirza/nodes",
    tags=["Mirza Node Management"],
)


class MirzaNodeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=10)
    address: str = Field(min_length=1, max_length=255)
    tunnel_address: Optional[str] = Field(
        default=None,
        max_length=255,
    )
    protocol: str = "tcp"
    ovpn_port: int = Field(default=1194, ge=1, le=65535)
    port: int = Field(ge=1, le=65535)
    key: str = Field(min_length=10, max_length=40)
    status: bool = True

    @field_validator("name", "address", "key")
    @classmethod
    def strip_required_fields(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Field cannot be empty")

        return value

    @field_validator("tunnel_address")
    @classmethod
    def strip_optional_address(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()

        return value or None

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, value: str) -> str:
        value = value.strip().lower()

        if value not in {"tcp", "udp"}:
            raise ValueError(
                "Protocol must be tcp or udp"
            )

        return value


class MirzaNodeUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=10,
    )
    address: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    tunnel_address: Optional[str] = Field(
        default=None,
        max_length=255,
    )
    protocol: Optional[str] = None
    ovpn_port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
    )
    port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
    )
    key: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=40,
    )
    status: Optional[bool] = None

    @field_validator("name", "address", "key")
    @classmethod
    def strip_optional_required_fields(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Field cannot be empty")

        return value

    @field_validator("protocol")
    @classmethod
    def validate_optional_protocol(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        value = value.strip().lower()

        if value not in {"tcp", "udp"}:
            raise ValueError(
                "Protocol must be tcp or udp"
            )

        return value


class MirzaNodeProbe(BaseModel):
    address: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    key: str = Field(min_length=10, max_length=40)


def require_mirza_key(
    x_mirza_key: str = Header(
        ...,
        alias="X-Mirza-Key",
    ),
) -> None:
    expected = (
        config.MIRZA_API_KEY or ""
    ).strip()

    supplied = x_mirza_key.strip()

    if (
        not expected
        or not supplied
        or not secrets.compare_digest(
            supplied,
            expected,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid integration API key",
        )


def assigned_user_count(
    db: Session,
    node_id: int,
) -> int:
    return (
        db.query(UserNode)
        .filter(UserNode.node_id == node_id)
        .count()
    )


def serialize_node(
    db: Session,
    node: Node,
) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "address": node.address,
        "tunnel_address": node.tunnel_address,
        "protocol": node.protocol,
        "ovpn_port": node.ovpn_port,
        "port": node.port,
        "status": bool(node.status),
        "key_configured": bool(node.key),
        "assigned_users": assigned_user_count(
            db,
            node.id,
        ),
    }


def ensure_unique_node(
    db: Session,
    *,
    name: str,
    address: str,
    exclude_id: Optional[int] = None,
) -> None:
    name_query = db.query(Node).filter(
        Node.name == name
    )

    address_query = db.query(Node).filter(
        Node.address == address
    )

    if exclude_id is not None:
        name_query = name_query.filter(
            Node.id != exclude_id
        )

        address_query = address_query.filter(
            Node.id != exclude_id
        )

    if name_query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A node with this name already exists",
        )

    if address_query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A node with this API address "
                "already exists"
            ),
        )


def check_node_connection(
    address: str,
    port: int,
    key: str,
) -> bool:
    try:
        return bool(
            NodeRequests(
                address=address,
                port=port,
                api_key=key,
            ).check_node()
        )
    except Exception:
        return False


@router.get("")
def list_nodes(
    db: Session = Depends(get_db),
    _: None = Depends(require_mirza_key),
):
    nodes = (
        db.query(Node)
        .order_by(Node.id)
        .all()
    )

    return {
        "success": True,
        "data": [
            serialize_node(db, node)
            for node in nodes
        ],
    }


@router.get("/{node_id}")
def get_node(
    node_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_mirza_key),
):
    node = (
        db.query(Node)
        .filter(Node.id == node_id)
        .first()
    )

    if not node:
        raise HTTPException(
            status_code=404,
            detail="Node not found",
        )

    return {
        "success": True,
        "data": serialize_node(db, node),
    }


@router.post("/probe")
def probe_node(
    request: MirzaNodeProbe,
    _: None = Depends(require_mirza_key),
):
    reachable = check_node_connection(
        request.address.strip(),
        request.port,
        request.key.strip(),
    )

    return {
        "success": reachable,
        "reachable": reachable,
    }


@router.post("")
def create_node(
    request: MirzaNodeCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_mirza_key),
):
    ensure_unique_node(
        db,
        name=request.name,
        address=request.address,
    )

    if not check_node_connection(
        request.address,
        request.port,
        request.key,
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "OV-Node API is not reachable "
                "with the supplied settings"
            ),
        )

    node = Node(
        name=request.name,
        address=request.address,
        tunnel_address=request.tunnel_address,
        protocol=request.protocol,
        ovpn_port=request.ovpn_port,
        port=request.port,
        key=request.key,
        status=request.status,
    )

    db.add(node)
    db.commit()
    db.refresh(node)

    return {
        "success": True,
        "message": "Node created successfully",
        "data": serialize_node(db, node),
    }


@router.put("/{node_id}")
def update_node(
    node_id: int,
    request: MirzaNodeUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_mirza_key),
):
    node = (
        db.query(Node)
        .filter(Node.id == node_id)
        .first()
    )

    if not node:
        raise HTTPException(
            status_code=404,
            detail="Node not found",
        )

    updates = request.model_dump(
        exclude_unset=True
    )

    new_name = updates.get(
        "name",
        node.name,
    )

    new_address = updates.get(
        "address",
        node.address,
    )

    ensure_unique_node(
        db,
        name=new_name,
        address=new_address,
        exclude_id=node.id,
    )

    current_assignments = assigned_user_count(
        db,
        node.id,
    )

    if (
        "name" in updates
        and updates["name"] != node.name
        and current_assignments > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Node name cannot be changed while "
                "users are assigned to it"
            ),
        )

    test_address = updates.get(
        "address",
        node.address,
    )

    test_port = updates.get(
        "port",
        node.port,
    )

    test_key = updates.get(
        "key",
        node.key,
    )

    connection_fields_changed = any(
        field in updates
        for field in ("address", "port", "key")
    )

    if (
        connection_fields_changed
        and not check_node_connection(
            test_address,
            test_port,
            test_key,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "New OV-Node API settings "
                "did not pass the connection test"
            ),
        )

    for field, value in updates.items():
        setattr(node, field, value)

    db.commit()
    db.refresh(node)

    profile_warning = any(
        field in updates
        for field in (
            "tunnel_address",
            "protocol",
            "ovpn_port",
        )
    )

    return {
        "success": True,
        "message": "Node updated successfully",
        "warning": (
            "Existing OVPN profiles may still contain "
            "the previous connection settings"
            if profile_warning
            else None
        ),
        "data": serialize_node(db, node),
    }


@router.post("/{node_id}/test")
def test_saved_node(
    node_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_mirza_key),
):
    node = (
        db.query(Node)
        .filter(Node.id == node_id)
        .first()
    )

    if not node:
        raise HTTPException(
            status_code=404,
            detail="Node not found",
        )

    reachable = check_node_connection(
        node.address,
        node.port,
        node.key,
    )

    return {
        "success": reachable,
        "reachable": reachable,
        "node_id": node.id,
        "name": node.name,
    }


@router.delete("/{node_id}")
def delete_node(
    node_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_mirza_key),
):
    node = (
        db.query(Node)
        .filter(Node.id == node_id)
        .first()
    )

    if not node:
        raise HTTPException(
            status_code=404,
            detail="Node not found",
        )

    assignments = assigned_user_count(
        db,
        node.id,
    )

    if assignments > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Node has {assignments} assigned users "
                "and cannot be deleted"
            ),
        )

    db.delete(node)
    db.commit()

    return {
        "success": True,
        "message": "Node deleted successfully",
        "node_id": node_id,
    }
