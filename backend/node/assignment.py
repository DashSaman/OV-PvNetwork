from __future__ import annotations

import asyncio

# OV_FAILOPEN_EVENTLOOP_V1
from typing import Optional

from sqlalchemy.orm import Session

from backend.db import crud
from backend.db.models import Node, UserNode
from backend.logger import logger
from backend.node.requests import NodeRequests


def validate_node_ids(
    db: Session,
    node_ids: Optional[list[int]],
) -> list[int]:
    """
    node_ids=None means all currently active nodes.
    An explicit list means only those nodes.
    """

    if node_ids is None:
        active_nodes = (
            db.query(Node)
            .filter(Node.status.is_(True), Node.drain.is_(False))
            .order_by(Node.id)
            .all()
        )

        if not active_nodes:
            raise ValueError("No active OpenVPN nodes are available")

        return [node.id for node in active_nodes]

    cleaned: list[int] = []

    for raw_node_id in node_ids:
        try:
            node_id = int(raw_node_id)
        except (TypeError, ValueError):
            raise ValueError("Every node ID must be an integer")

        if node_id <= 0:
            raise ValueError("Node IDs must be positive integers")

        if node_id not in cleaned:
            cleaned.append(node_id)

    if not cleaned:
        raise ValueError("At least one node must be selected")

    nodes = (
        db.query(Node)
        .filter(Node.id.in_(cleaned))
        .order_by(Node.id)
        .all()
    )

    found_ids = {node.id for node in nodes}
    missing_ids = [
        node_id
        for node_id in cleaned
        if node_id not in found_ids
    ]

    if missing_ids:
        raise ValueError(
            "Unknown node IDs: "
            + ", ".join(str(item) for item in missing_ids)
        )

    inactive_ids = [
        node.id
        for node in nodes
        if not node.status
    ]

    if inactive_ids:
        raise ValueError(
            "Inactive node IDs cannot be assigned: "
            + ", ".join(str(item) for item in inactive_ids)
        )


    draining_ids = [
        node.id
        for node in nodes
        if getattr(
            node,
            "drain",
            False,
        )
    ]

    if draining_ids:
        raise ValueError(
            "Draining node IDs cannot be assigned: "
            + ", ".join(
                str(item)
                for item in draining_ids
            )
        )

    return cleaned


def set_user_nodes(
    db: Session,
    user_uuid: str,
    node_ids: list[int],
) -> None:
    db.query(UserNode).filter(
        UserNode.user_uuid == user_uuid
    ).delete(synchronize_session=False)

    for node_id in node_ids:
        db.add(
            UserNode(
                user_uuid=user_uuid,
                node_id=node_id,
            )
        )

    db.commit()


def clear_user_nodes(
    db: Session,
    user_uuid: str,
) -> None:
    db.query(UserNode).filter(
        UserNode.user_uuid == user_uuid
    ).delete(synchronize_session=False)

    db.commit()


def get_explicit_node_ids(
    db: Session,
    user_uuid: str,
) -> list[int]:
    rows = (
        db.query(UserNode.node_id)
        .filter(UserNode.user_uuid == user_uuid)
        .order_by(UserNode.node_id)
        .all()
    )

    return [row[0] for row in rows]


def get_user_nodes(
    db: Session,
    user_uuid: str,
    active_only: bool = False,
) -> list[Node]:
    node_ids = get_explicit_node_ids(
        db,
        user_uuid,
    )

    query = db.query(Node)

    # Backward-compatible fallback for legacy users.
    if node_ids:
        query = query.filter(Node.id.in_(node_ids))

    if active_only:
        query = query.filter(Node.status.is_(True))

    return query.order_by(Node.id).all()


def user_can_access_node(
    db: Session,
    user_uuid: str,
    node_id: int,
) -> bool:
    node_ids = get_explicit_node_ids(
        db,
        user_uuid,
    )

    # Legacy users without records keep previous all-node access.
    if not node_ids:
        return True

    return node_id in node_ids


def _node_request(node: Node) -> NodeRequests:
    return NodeRequests(
        address=node.address,
        port=node.port,
        api_key=node.key,
    )


async def create_user_on_assigned_nodes(
    uuid: str,
    name: str,
    db: Session,
) -> list[int]:
    """
    Fail-open provisioning for Mirza users.

    user_nodes remains the desired assignment.
    Reachable nodes are provisioned immediately.
    Unreachable/maintenance/draining nodes stay assigned and are
    reconciled later by ov-node-user-reconcile.timer.
    """
    nodes = get_user_nodes(
        db,
        uuid,
        active_only=False,
    )

    if not nodes:
        raise RuntimeError(
            "No nodes are assigned to this user"
        )

    created_node_ids: list[int] = []
    pending_nodes: list[str] = []

    for node in nodes:
        if (
            not node.status
            or getattr(node, "drain", False)
            or getattr(node, "maintenance", False)
        ):
            pending_nodes.append(node.name)
            logger.warning(
                f"Provision pending for '{name}' on node "
                f"'{node.name}': node unavailable by control state"
            )
            continue

        request = _node_request(node)

        reachable = await asyncio.to_thread(
            request.check_node
        )

        if not reachable:
            pending_nodes.append(node.name)
            logger.warning(
                f"Provision pending for '{name}' on node "
                f"'{node.name}': node is not reachable"
            )
            continue

        client_name = f"{name}-{node.name}"

        created = await asyncio.to_thread(
            request.create_user,
            client_name,
        )

        if not created:
            pending_nodes.append(node.name)
            logger.warning(
                f"Provision pending for '{client_name}': "
                "create request failed and will be retried"
            )
            continue

        created_node_ids.append(node.id)
        logger.info(
            f"User '{client_name}' created on assigned node "
            f"{node.address}:{node.port}"
        )

    logger.info(
        f"Fail-open provisioning result for '{name}': "
        f"created={len(created_node_ids)} "
        f"pending={len(pending_nodes)} "
        f"pending_nodes={pending_nodes}"
    )

    return created_node_ids


async def change_user_status_on_assigned_nodes(
    uuid: str,
    name: str,
    status: bool,
    db: Session,
) -> bool:
    nodes = get_user_nodes(
        db,
        uuid,
        active_only=False,
    )

    success = True

    for node in nodes:
        if not node.status:
            logger.warning(
                f"Skipping inactive assigned node: {node.name}"
            )
            success = False
            continue

        request = _node_request(node)

        if not await asyncio.to_thread(request.check_node):
            success = False
            continue

        if not await asyncio.to_thread(
            request.change_user_status,
            f"{name}-{node.name}",
            status,
        ):
            success = False

    crud.change_user_status(
        db,
        uuid,
        status,
    )

    return success


async def delete_user_on_assigned_nodes(
    uuid: str,
    name: str,
    db: Session,
) -> bool:
    nodes = get_user_nodes(
        db,
        uuid,
        active_only=False,
    )

    success = True

    for node in nodes:
        if not node.status:
            logger.warning(
                f"Could not delete user from inactive node: "
                f"{node.name}"
            )
            success = False
            continue

        request = _node_request(node)

        if not await asyncio.to_thread(request.check_node):
            success = False
            continue

        if not await asyncio.to_thread(
            request.delete_user,
            f"{name}-{node.name}",
        ):
            success = False

    return success


async def replace_user_node_assignments(
    user_uuid: str,
    name: str,
    node_ids: list[int],
    db: Session,
) -> dict:
    """Safely replace desired node assignments without deleting live profiles.

    Removed nodes are deactivated first (reversible) instead of deleting their
    certificate/profile. Added nodes are provisioned fail-open; unavailable
    nodes remain desired assignments and are left for the existing reconciler.
    """
    user = crud.get_user_by_uuid(db, user_uuid)
    if user is None:
        raise ValueError("User not found")

    desired_ids: list[int] = []
    for raw in node_ids:
        try:
            node_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Every node ID must be an integer") from exc
        if node_id <= 0:
            raise ValueError("Node IDs must be positive integers")
        if node_id not in desired_ids:
            desired_ids.append(node_id)
    if not desired_ids:
        raise ValueError("At least one node must be selected")

    desired_nodes = (
        db.query(Node)
        .filter(Node.id.in_(desired_ids))
        .order_by(Node.id)
        .all()
    )
    found = {int(node.id) for node in desired_nodes}
    missing = [item for item in desired_ids if item not in found]
    if missing:
        raise ValueError("Unknown node IDs: " + ", ".join(map(str, missing)))

    current_nodes = get_user_nodes(db, user_uuid, active_only=False)
    current_ids = {int(node.id) for node in current_nodes}
    desired_set = set(desired_ids)
    added_ids = desired_set - current_ids
    removed_ids = current_ids - desired_set

    by_id = {int(node.id): node for node in desired_nodes}
    invalid_added = [
        node_id for node_id in sorted(added_ids)
        if (
            not by_id[node_id].status
            or getattr(by_id[node_id], "drain", False)
            or getattr(by_id[node_id], "maintenance", False)
        )
    ]
    if invalid_added:
        raise ValueError(
            "Unavailable nodes cannot be newly assigned: "
            + ", ".join(map(str, invalid_added))
        )

    current_by_id = {int(node.id): node for node in current_nodes}
    disabled_removed: list[int] = []
    try:
        for node_id in sorted(removed_ids):
            node = current_by_id[node_id]
            if not node.status:
                raise RuntimeError(
                    f"Cannot remove assignment from offline node '{node.name}' safely"
                )
            request = _node_request(node)
            if not await asyncio.to_thread(request.check_node):
                raise RuntimeError(
                    f"Cannot remove assignment while node '{node.name}' is unreachable"
                )
            client_name = f"{name}-{node.name}"
            if not await asyncio.to_thread(
                request.change_user_status,
                client_name,
                False,
            ):
                raise RuntimeError(
                    f"Could not deactivate '{client_name}' before unassignment"
                )
            disabled_removed.append(node_id)
    except Exception:
        if bool(user.is_active):
            for node_id in disabled_removed:
                node = current_by_id[node_id]
                request = _node_request(node)
                try:
                    await asyncio.to_thread(
                        request.change_user_status,
                        f"{name}-{node.name}",
                        True,
                    )
                except Exception:
                    logger.exception(
                        f"Could not restore assignment status on node {node.name}"
                    )
        raise

    # The reversible remote deactivation gate passed. Persist desired state.
    set_user_nodes(db, user_uuid, desired_ids)

    provisioned: list[int] = []
    pending: list[int] = []
    for node_id in sorted(added_ids):
        node = by_id[node_id]
        request = _node_request(node)
        if not await asyncio.to_thread(request.check_node):
            pending.append(node_id)
            continue
        client_name = f"{name}-{node.name}"
        created = await asyncio.to_thread(request.create_user, client_name)
        if not created:
            # A stale disabled profile may already exist after a previous
            # unassignment. Re-using it avoids unnecessary certificate churn.
            if await asyncio.to_thread(
                request.change_user_status,
                client_name,
                bool(user.is_active),
            ):
                provisioned.append(node_id)
            else:
                pending.append(node_id)
            continue
        if not bool(user.is_active):
            if not await asyncio.to_thread(
                request.change_user_status,
                client_name,
                False,
            ):
                # Do not leave a newly-created client active for an inactive user.
                await asyncio.to_thread(request.delete_user, client_name)
                pending.append(node_id)
                continue
        provisioned.append(node_id)

    return {
        "desired_node_ids": sorted(desired_ids),
        "added_node_ids": sorted(added_ids),
        "removed_node_ids": sorted(removed_ids),
        "disabled_removed_node_ids": sorted(disabled_removed),
        "provisioned_node_ids": sorted(provisioned),
        "pending_node_ids": sorted(pending),
    }
