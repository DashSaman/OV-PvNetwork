import asyncio
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.logger import logger
from backend.schema._input import NodeCreate
from .requests import NodeRequests
from backend.db import crud
from backend.db.models import Node


async def add_node_handler(request: NodeCreate, db: Session) -> bool:
    new_node = NodeRequests(
        request.address,
        request.port,
        request.key,
        request.tunnel_address,
        request.protocol,
        request.ovpn_port,
        request.set_new_setting,
    )
    if await asyncio.to_thread(new_node.check_node):
        crud.create_node(db, request)
        logger.info(f"Node added successfully: {request.address}:{request.port}")
        return True
    else:
        logger.warning(f"Failed to add node: {request.address}:{request.port}")
        return False


async def update_node_handler(node_id: int, request: NodeCreate, db: Session) -> bool:
    """Update a node"""
    crud.update_node(db, node_id, request)
    restart_request = NodeRequests(
        address=request.address,
        port=request.port,
        api_key=request.key,
        tunnel_address=request.tunnel_address,
        protocol=request.protocol,
        ovpn_port=request.ovpn_port,
        set_new_setting=True,
    )
    restart_node = await asyncio.to_thread(restart_request.check_node)

    logger.info(f"Node updated successfully: {request.address}:{request.port}")
    return restart_node


async def delete_node_handler(node_id: int, db: Session) -> bool:
    """Delete a node"""
    node = crud.get_node_by_id(db, node_id)
    if node:
        crud.delete_node(db, node.id)
        logger.info(f"Node deleted successfully: {node.name}")
        return True
    else:
        logger.warning(f"Failed to delete node: {node.name}")
        return False


async def list_nodes_handler(db: Session) -> list:
    """Retrieve all nodes"""
    nodes_list = []
    nodes = crud.get_all_nodes(db)
    for node in nodes:
        node_info = {
            "id": node.id,
            "name": node.name,
            "address": node.address,
            "tunnel-address": node.tunnel_address,
            "ovpn_port": node.ovpn_port,
            "protocol": node.protocol,
            "port": node.port,
            "status": "active" if node.status else "inactive",
        }
        nodes_list.append(node_info)
    return nodes_list


async def get_node_status_handler(node_id: int, db: Session):
    """Get node status without blocking the API event loop."""
    node = crud.get_node_by_id(db, node_id)
    if not node:
        return None

    # PVNETWORK_FAILOPEN_EVENTLOOP_V1
    address = str(node.address)
    port = int(node.port)
    api_key = str(node.key)
    enabled = bool(node.status)

    # Release any DB transaction before waiting for a remote node.
    db.rollback()
    db.close()

    try:
        node_status = await asyncio.wait_for(
            asyncio.to_thread(
                NodeRequests(
                    address=address,
                    port=port,
                    api_key=api_key,
                ).get_node_info
            ),
            timeout=6.0,
        )
    except Exception:
        node_status = {}

    return {
        "address": address,
        "port": port,
        "status": "active" if enabled else "inactive",
        "node_info": node_status,
    }


async def create_user_on_all_nodes(name: str, db: Session):
    """Create a user on all nodes"""
    nodes = crud.get_all_nodes(db)
    if nodes:
        for node in nodes:
            node_requests = NodeRequests(
                address=node.address, port=node.port, api_key=node.key
            )
            node_status = await asyncio.to_thread(node_requests.check_node)
            if node_status:
                await asyncio.to_thread(node_requests.create_user, f"{name}-{node.name}")
                logger.info(
                    f"User '{name}-{node.name}' created on node {node.address}:{node.port}"
                )
            else:
                logger.warning(
                    f"Failed to create user '{name}-{node.name}' on node {node.address}:{node.port}"
                )


async def change_user_status_on_all_nodes(
    uuid: str, name: str, status: bool, db: Session
):
    nodes = crud.get_all_nodes(db)
    crud.change_user_status(db, uuid, status)

    if nodes:
        for node in nodes:
            node_request = NodeRequests(
                address=node.address, port=node.port, api_key=node.key
            )
            node_status = await asyncio.to_thread(node_request.check_node)
            if node_status:
                await asyncio.to_thread(node_request.change_user_status, f"{name}-{node.name}", status)
                logger.info(
                    f"User '{name}-{node.name}' changed status on node {node.address}:{node.port}"
                )
            else:
                logger.warning(
                    f"Failed to chang user status '{name}-{node.name}' on node {node.address}:{node.port}"
                )


async def download_ovpn_client_from_node(
    uuid: str,
    node_id: int,
    db: Session,
):
    import asyncio
    import re

    from fastapi.responses import (
        Response as FastAPIResponse,
    )

    node = crud.get_node_by_id(
        db,
        node_id,
    )

    user = crud.get_user_by_uuid(
        db,
        uuid,
    )

    if not node or not user:
        return None

    client_name = (
        f"{user.name}-{node.name}"
    )

    request = NodeRequests(
        address=node.address,
        port=node.port,
        api_key=node.key,
        tunnel_address=(
            node.tunnel_address
            or node.address
        ),
        protocol=(
            node.protocol
            or "udp"
        ),
        ovpn_port=int(
            node.ovpn_port
            or 1194
        ),
        set_new_setting=False,
    )

    def raw_bytes(result):

        if result is None:
            return b""

        raw = getattr(
            result,
            "body",
            None,
        )

        if raw is None:
            raw = getattr(
                result,
                "content",
                None,
            )

        if raw is None:
            if isinstance(
                result,
                (bytes, bytearray),
            ):
                raw = bytes(result)

        if isinstance(raw, str):
            raw = raw.encode(
                "utf-8"
            )

        return bytes(
            raw or b""
        )

    def valid(result):

        raw = raw_bytes(
            result
        )

        if len(raw) < 500:
            return False

        text = raw.decode(
            "utf-8",
            errors="ignore",
        ).lower()

        return all(
            marker in text
            for marker in (
                "<ca>",
                "</ca>",
                "<cert>",
                "</cert>",
                "<key>",
                "</key>",
            )
        )

    result = await asyncio.to_thread(
        request.download_ovpn_client,
        client_name,
    )

    if not valid(result):

        await asyncio.to_thread(
            request.create_user,
            client_name,
        )

        result = await asyncio.to_thread(
            request.download_ovpn_client,
            client_name,
        )

    if not valid(result):

        logger.error(
            "No valid OVPN profile for %s",
            client_name,
        )

        return None

    text = raw_bytes(
        result
    ).decode(
        "utf-8",
        errors="replace",
    )

    desired_remote = (
        f"remote "
        f"{node.tunnel_address or node.address} "
        f"{int(node.ovpn_port or 1194)}"
    )

    desired_proto = (
        f"proto "
        f"{node.protocol or 'udp'}"
    )

    lines = []

    for line in text.splitlines():

        if re.match(
            r"^\\s*remote\\s+",
            line,
            flags=re.I,
        ):
            continue

        if re.match(
            r"^\\s*proto\\s+",
            line,
            flags=re.I,
        ):
            continue

        lines.append(line)

    normalized = (
        desired_remote
        + "\n"
        + desired_proto
        + "\n"
        + "\n".join(lines)
        + "\n"
    )

    return FastAPIResponse(
        content=normalized.encode(
            "utf-8"
        ),
        media_type=(
            "application/x-openvpn-profile"
        ),
        headers={
            "Content-Disposition":
                f'attachment; filename="{client_name}.ovpn"',

            "Cache-Control":
                "no-store",

            "X-Content-Type-Options":
                "nosniff",
        },
    )




async def delete_user_on_all_nodes(name: str, db: Session) -> dict:
    """Best-effort concurrent removal from every node.

    PVNETWORK_DELETE_USER_REUSE_V7
    Database deletion is decided by the caller. A temporarily unavailable
    node must not keep a username locked forever in the panel database.
    """
    nodes = crud.get_all_nodes(db)
    if not nodes:
        return {"all_ok": True, "deleted": [], "failed": []}

    async def remove_from_node(node):
        node_requests = NodeRequests(
            address=node.address, port=node.port, api_key=node.key
        )
        client_name = f"{name}-{node.name}"
        reachable = await asyncio.to_thread(node_requests.check_node)
        if not reachable:
            logger.warning(
                f"Could not reach node while deleting '{client_name}': "
                f"{node.address}:{node.port}"
            )
            return {"node_id": node.id, "node": node.name, "ok": False, "reason": "unreachable"}

        removed = await asyncio.to_thread(node_requests.delete_user, client_name)
        if removed:
            logger.info(
                f"User '{client_name}' deleted on node {node.address}:{node.port}"
            )
            return {"node_id": node.id, "node": node.name, "ok": True}

        logger.warning(
            f"Node did not confirm deletion of '{client_name}' on "
            f"{node.address}:{node.port}"
        )
        return {"node_id": node.id, "node": node.name, "ok": False, "reason": "not_confirmed"}

    results = await asyncio.gather(
        *(remove_from_node(node) for node in nodes),
        return_exceptions=True,
    )
    deleted = []
    failed = []
    for node, result in zip(nodes, results):
        if isinstance(result, Exception):
            logger.error(
                f"Unexpected node deletion error for {name}-{node.name}: {result}"
            )
            failed.append({"node_id": node.id, "node": node.name, "reason": str(result)[:250]})
        elif result.get("ok"):
            deleted.append(result)
        else:
            failed.append(result)
    return {"all_ok": not failed, "deleted": deleted, "failed": failed}


async def get_users_used_traffic(node: Node, db: Session) -> dict:
    """Geting users usage on node"""
    node_requests = NodeRequests(address=node.address, port=node.port, api_key=node.key)
    response = await asyncio.to_thread(node_requests.get_users_usage)

    if not response:
        return {}
    return response.get("users", {})
