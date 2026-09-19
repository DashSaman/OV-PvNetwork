from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user
from backend.db.engine import get_db
from backend.db import crud
from backend.schema.output import ResponseModel
from backend.schema._input import NodeCreate
from backend.node.health import (
    build_nodes_health,
    decorate_node_list,
    update_node_control,
)
from backend.node.task import (
    add_node_handler,
    update_node_handler,
    delete_node_handler,
    download_ovpn_client_from_node,
    list_nodes_handler,
    get_node_status_handler,
)

router = APIRouter(prefix="/nodes", tags=["Nodes"])


# PVNETWORK_NODE_HEALTH_CONTROL_V1
class NodeControlUpdate(BaseModel):
    drain: Optional[bool] = None
    weight: Optional[int] = Field(
        default=None,
        ge=0,
        le=1000,
    )


@router.get("/public-health/", response_model=ResponseModel)
async def public_nodes_health(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    data = await build_nodes_health(db)
    safe = [{
        "id": item.get("id"), "name": item.get("name"),
        "health": item.get("health"), "enabled": item.get("enabled"),
        "drain": item.get("drain"),
        "online_users": item.get("central_online_users", 0),
        "active_sessions": item.get("central_active_sessions", 0),
        "eligible": item.get("eligible_for_new_connections", False),
    } for item in data]
    return ResponseModel(success=True, msg="Public node health retrieved", data=safe)


@router.get(
    "/health/",
    response_model=ResponseModel,
)
async def get_nodes_health(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user["type"] != "main_admin":
        return ResponseModel(
            success=False,
            msg="Unauthorized access",
            data=None,
        )

    data = await build_nodes_health(
        db
    )

    return ResponseModel(
        success=True,
        msg="Node health retrieved successfully",
        data=data,
    )


@router.put(
    "/{node_id}/control",
    response_model=ResponseModel,
)
async def update_node_control_api(
    node_id: int,
    request: NodeControlUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user["type"] != "main_admin":
        return ResponseModel(
            success=False,
            msg="Unauthorized access",
            data=None,
        )

    try:
        data = update_node_control(
            db,
            node_id,
            drain=request.drain,
            weight=request.weight,
        )

    except ValueError as exc:
        return ResponseModel(
            success=False,
            msg=str(exc),
            data=None,
        )

    return ResponseModel(
        success=True,
        msg="Node control updated successfully",
        data=data,
    )




@router.post("/", response_model=ResponseModel)
async def add_node(
    request: NodeCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user["type"] != "main_admin":
        return ResponseModel(success=False, msg="Unauthorized access", data=None)

    new_node = await add_node_handler(request, db)
    return ResponseModel(
        success=new_node,
        msg="Node added successfully" if new_node else "Failed to add node",
    )


@router.put("/{node_id}", response_model=ResponseModel)
async def update_node(
    node_id: int,
    request: NodeCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user["type"] != "main_admin":
        return ResponseModel(success=False, msg="Unauthorized access", data=None)

    result = await update_node_handler(node_id, request, db)
    return ResponseModel(
        success=result,
        msg="Node updated successfully" if result else "Failed to update node",
    )


@router.get("/{node_id}/status/", response_model=ResponseModel)
async def get_node_status(
    node_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user["type"] != "main_admin":
        return ResponseModel(success=False, msg="Unauthorized access", data=None)

    node_status = await get_node_status_handler(node_id, db)
    return ResponseModel(
        success=True,
        msg="Node status retrieved successfully",
        data=node_status,
    )


@router.get("/", response_model=ResponseModel)
async def list_nodes(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    nodes = decorate_node_list(
        db,
        await list_nodes_handler(db),
    )
    if user["type"] == "admin":
        # Resellers only receive operational capacity data. Never expose
        # addresses, ports, API keys or tunnel configuration.
        nodes = [{
            "id": item.get("id"),
            "name": item.get("name"),
            "status": item.get("status"),
            "drain": item.get("drain", False),
            "online": item.get("online", item.get("is_online", item.get("status"))),
            "online_count": item.get("online_count", 0),
            "assigned_users": item.get("assigned_users", 0),
        } for item in nodes]
    return ResponseModel(
        success=True,
        msg="Nodes retrieved successfully",
        data=nodes,
    )


@router.get(
    "/ovpn/{uuid}/{node_id}",
    description="Download OVPN client configuration from a node",
)
async def download_ovpn_client(
    node_id: int,
    uuid: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    target = crud.get_user_by_uuid(db, uuid)
    if target is None or (user["type"] == "admin" and target.owner != user["username"]):
        return ResponseModel(success=False, msg="User not found", data=None)
    response = await download_ovpn_client_from_node(db=db, uuid=uuid, node_id=node_id)
    if response:
        return response
    else:
        return ResponseModel(success=False, msg="OVPN file not found", data=None)


@router.delete("/{node_id}", response_model=ResponseModel)
async def delete_node(
    node_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # PVNETWORK_SAFE_NODE_DELETE_V2
    from backend.db.models import Node, UserNode

    if user["type"] != "main_admin":
        raise HTTPException(
            status_code=403,
            detail="Main administrator access is required",
        )

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

    if db.query(Node).count() <= 1:
        raise HTTPException(
            status_code=409,
            detail="The last remaining node cannot be deleted.",
        )

    assignments = (
        db.query(UserNode)
        .filter(UserNode.node_id == node_id)
        .all()
    )

    unsafe_users = []

    for assignment in assignments:
        alternatives = (
            db.query(UserNode)
            .join(
                Node,
                Node.id == UserNode.node_id,
            )
            .filter(
                UserNode.user_uuid
                == assignment.user_uuid,
                UserNode.node_id != node_id,
                Node.status.is_(True),
            )
            .count()
        )

        if alternatives < 1:
            unsafe_users.append(
                str(assignment.user_uuid)
            )

    if unsafe_users:
        raise HTTPException(
            status_code=409,
            detail=(
                "Node cannot be deleted because "
                f"{len(unsafe_users)} assigned users "
                "have no other active node."
            ),
        )

    try:
        if assignments:
            (
                db.query(UserNode)
                .filter(
                    UserNode.node_id == node_id
                )
                .delete(
                    synchronize_session=False
                )
            )

        result = await delete_node_handler(
            node_id,
            db,
        )

        if not result:
            db.rollback()

            raise HTTPException(
                status_code=500,
                detail="Node deletion failed",
            )

        return ResponseModel(
            success=True,
            msg="Node deleted successfully",
            data={
                "node_id": node_id,
                "removed_assignments":
                    len(assignments),
            },
        )

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Node deletion failed: {exc}",
        )


# PVNETWORK_AUTO_NODE_DEPLOY_V3
import threading
import urllib.error
import urllib.request

from backend.node.deploy import (
    deploy_node,
    fail_job,
    finish_job,
    get_deploy_job,
    host_deploy_lock,
    new_deploy_job,
    update_job,
)
from backend.db import crud
from backend.db.engine import SessionLocal
from backend.db.models import Node

class AutoNodeDeployRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    address: str
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(default="root", min_length=1, max_length=64)
    ssh_password: str = Field(min_length=1, max_length=512)
    ssh_fingerprint: Optional[str] = Field(default=None, max_length=160)
    panel_ip: str
    protocol: str = "udp"
    ovpn_port: int = Field(default=1194, ge=1, le=65535)
    node_port: int = Field(default=9090, ge=1, le=65535)
    tunnel_address: Optional[str] = None

def _verify_node_from_panel(
    address: str,
    port: int,
    api_key: str,
    tunnel_address: str,
    protocol: str,
    ovpn_port: int,
) -> None:
    """Verify authenticated panel-to-node communication."""
    from backend.node.requests import NodeRequests

    client = NodeRequests(
        address=address,
        port=port,
        api_key=api_key,
        tunnel_address=tunnel_address or address,
        protocol=protocol,
        ovpn_port=ovpn_port,
        set_new_setting=True,
    )

    if not client.check_node():
        raise RuntimeError(
            f"Panel-to-node /sync/status failed for {address}:{port}"
        )


# PVNETWORK_AUTO_SYNC_NEW_NODE_V1
def _normalize_auto_node_name(raw_name: str, address: str) -> str:
    """
    Node names are also used inside OpenVPN certificate/client names.
    Keep them automatically safe for EasyRSA/OpenVPN.
    """
    import re

    name = str(raw_name or "").strip()

    name = re.sub(
        r"[^0-9A-Za-z_-]+",
        "_",
        name,
    )

    name = re.sub(r"_+", "_", name).strip("_-")

    if not name:
        name = (
            "node_"
            + re.sub(
                r"[^0-9A-Za-z]+",
                "_",
                str(address),
            ).strip("_")
        )

    return name[:48]


def _sync_existing_assignments_to_node(db, node) -> dict:
    """Provision only legacy all-node users on a newly installed node.

    Users with any explicit ``user_nodes`` rows own an authoritative node set
    and must never be widened just because a new node is registered. Legacy
    users without assignment rows retain the historical all-available-node
    fallback, so they are provisioned on the new node without creating rows.
    """
    from backend.db.models import User, UserNode
    from backend.node.requests import NodeRequests

    explicitly_assigned = {
        str(row[0])
        for row in db.query(UserNode.user_uuid).distinct().all()
    }
    users = [
        user
        for user in (
            db.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.id)
            .all()
        )
        if str(user.uuid) not in explicitly_assigned
    ]

    if not users:
        return {
            "assigned": 0,
            "attempted": 0,
            "created": 0,
            "failed": 0,
        }

    request = NodeRequests(
        address=node.address,
        port=node.port,
        api_key=node.key,
        tunnel_address=node.tunnel_address or node.address,
        protocol=node.protocol,
        ovpn_port=node.ovpn_port,
        set_new_setting=False,
    )

    if not request.check_node():
        return {
            "assigned": 0,
            "attempted": 0,
            "created": 0,
            "failed": len(users),
            "reason": "node unreachable; reconciler will retry",
        }

    created_count = 0
    failed_count = 0
    for user in users:
        client_name = f"{user.name}-{node.name}"
        try:
            if request.create_user(client_name):
                created_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1

    return {
        "assigned": 0,
        "attempted": len(users),
        "created": created_count,
        "failed": failed_count,
    }



def _run_deploy_job(job, request_data: dict) -> None:
    lock = host_deploy_lock(request_data["address"])
    if not lock.acquire(blocking=False):
        fail_job(job, RuntimeError("Another deployment is already running for this address"))
        return
    db = SessionLocal()
    try:
        job.state = "running"

        request_data["name"] = _normalize_auto_node_name(
            request_data["name"],
            request_data["address"],
        )

        update_job(job, 1, "preflight", "Validating deployment request")
        duplicate = db.query(Node).filter(
            (Node.address == request_data["address"]) |
            (Node.name == request_data["name"])
        ).first()
        if duplicate:
            raise RuntimeError("A node with this name or address already exists")

        result = deploy_node(
            host=request_data["address"],
            ssh_port=request_data["ssh_port"],
            username=request_data["ssh_username"],
            password=request_data["ssh_password"],
            expected_fingerprint=request_data.get("ssh_fingerprint"),
            api_port=request_data["node_port"],
            ovpn_port=request_data["ovpn_port"],
            protocol=request_data["protocol"],
            panel_ip=request_data["panel_ip"],
            reporter=lambda p, s, m, level="info": update_job(job, p, s, m, level),
        )
        # Drop the password reference as soon as SSH work is complete.
        request_data["ssh_password"] = ""
        update_job(job, 96, "panel_health", "Verifying /sync/status from the panel")
        _verify_node_from_panel(
            address=result.address,
            port=result.api_port,
            api_key=result.api_key,
            tunnel_address=(
                request_data.get("tunnel_address") or result.address
            ),
            protocol=result.protocol,
            ovpn_port=result.ovpn_port,
        )

        update_job(job, 98, "database", "Registering verified node")
        node_request = NodeCreate(
            name=request_data["name"], address=result.address,
            tunnel_address=(request_data.get("tunnel_address") or result.address),
            protocol=result.protocol, ovpn_port=result.ovpn_port,
            port=result.api_port, key=result.api_key,
            status=True, set_new_setting=False,
        )
        created = crud.create_node(db, node_request)

        if created is False:
            raise RuntimeError("Database registration failed")

        db.commit()

        update_job(
            job,
            99,
            "user_sync",
            "Synchronizing existing users to new node",
        )

        try:
            sync_summary = _sync_existing_assignments_to_node(
                db,
                created,
            )
        except Exception as sync_exc:
            db.rollback()

            sync_summary = {
                "assigned": 0,
                "attempted": 0,
                "created": 0,
                "failed": -1,
                "error": str(sync_exc)[:500],
            }


        # Explicit user-node assignments are authoritative. A new node must
        # never widen those sets. Queue reconciliation only to repair legacy
        # all-node users or previously pending profiles.
        try:
            import subprocess

            subprocess.Popen(
                [
                    "systemctl",
                    "start",
                    "--no-block",
                    "pvnetwork-node-user-reconcile.service",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            update_job(
                job,
                99,
                "user_sync",
                "Queued reconciliation without widening explicit assignments",
            )
        except Exception as sync_error:
            update_job(
                job,
                99,
                "user_sync",
                f"Node registered; reconciliation warning: {sync_error}",
            )

        finish_job(job, {
            "address": result.address,
            "port": result.api_port,
            "fingerprint": result.fingerprint,
            "name": created.name,
            "user_sync": sync_summary,
        })
    except Exception as exc:
        db.rollback()
        fail_job(job, exc)
    finally:
        request_data["ssh_password"] = ""
        db.close()
        lock.release()


@router.post("/deploy/", response_model=ResponseModel)
async def auto_deploy_node(request: AutoNodeDeployRequest, user: dict = Depends(get_current_user)):
    if user["type"] != "main_admin":
        return ResponseModel(success=False, msg="Unauthorized access", data=None)
    data = request.model_dump()
    job = new_deploy_job(request.address)
    threading.Thread(target=_run_deploy_job, args=(job, data), daemon=True).start()
    return ResponseModel(success=True, msg="Deployment started", data={"job_id": job.id})


@router.get("/deploy/{job_id}/", response_model=ResponseModel)
async def deploy_node_status(job_id: str, user: dict = Depends(get_current_user)):
    if user["type"] != "main_admin":
        return ResponseModel(success=False, msg="Unauthorized access", data=None)
    job = get_deploy_job(job_id)
    if not job:
        return ResponseModel(success=False, msg="Deployment job not found", data=None)
    return ResponseModel(success=True, msg="Deployment status", data=job)
