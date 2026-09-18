import asyncio

from backend.logger import logger
from backend.db import crud
from backend.db.engine import get_db
from backend.node.task import get_users_used_traffic
from backend.node.assignment import (
    change_user_status_on_assigned_nodes,
    user_can_access_node,
)
from backend.operations.multinode_usage import (
    ensure_usage_table,
    get_last_usage,
    set_last_usage,
)


async def enforce_user_limits():
    """Disable expired users or users whose shared traffic pool is exhausted."""

    db = next(get_db())

    try:
        expired_users = crud.get_expired_users(db)
        exceeded_users = crud.get_users_exceeded_traffic(db)

        users_to_disable = {
            u.id: u
            for u in expired_users + exceeded_users
        }.values()

        for user in users_to_disable:
            user.is_active = False

            await change_user_status_on_assigned_nodes(
                uuid=user.uuid,
                name=user.name,
                status=False,
                db=db,
            )

            await asyncio.sleep(0.2)

        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error in users expiration check -> {e}",
            exc_info=True,
        )

    finally:
        db.close()


async def check_user_used_traffic():
    """
    Shared MultiNode accounting.

    Each user/node pair has its own last_usage counter.
    user.used is the shared total across all assigned nodes.
    """

    db = next(get_db())

    try:
        ensure_usage_table(db)
        db.commit()

        nodes = crud.get_all_nodes(db)

        if not nodes:
            logger.warning("No nodes found")
            return

        all_users = {
            u.name: u
            for u in crud.get_all_users(db)
        }

        for node in nodes:
            try:
                # OV_FAILOPEN_EVENTLOOP_V1
                # Do not hold an idle DB transaction while a remote node
                # is being queried. expire_on_commit=False keeps node fields.
                db.commit()

                users = await get_users_used_traffic(
                    node,
                    db=db,
                )

                if not users:
                    continue

                suffix = f"-{node.name}"

                for client_name, raw_used_bytes in users.items():

                    # MultiNode clients are stored as:
                    # base_username-NodeName
                    if not client_name.endswith(suffix):
                        logger.warning(
                            f"Cannot map client '{client_name}' "
                            f"to node '{node.name}'"
                        )
                        continue

                    clean_username = client_name[
                        :-len(suffix)
                    ]

                    user = all_users.get(clean_username)

                    if not user:
                        logger.warning(
                            f"User not found: {clean_username}"
                        )
                        continue

                    # Do not account stale clients on nodes
                    # not assigned to this user.
                    if not user_can_access_node(
                        db,
                        user.uuid,
                        node.id,
                    ):
                        logger.warning(
                            f"Ignoring unassigned usage: "
                            f"{clean_username} / {node.name}"
                        )
                        continue

                    try:
                        used_bytes = int(
                            raw_used_bytes or 0
                        )
                    except (TypeError, ValueError):
                        logger.warning(
                            f"Invalid usage for "
                            f"{client_name}: {raw_used_bytes}"
                        )
                        continue

                    last_usage = get_last_usage(
                        db,
                        user.uuid,
                        node.id,
                    )

                    # New users start from zero.
                    if last_usage is None:
                        last_usage = 0

                    # Normal increase
                    if used_bytes >= last_usage:
                        delta = used_bytes - last_usage

                    # OpenVPN counter reset after reconnect
                    else:
                        delta = used_bytes

                    if delta < 0:
                        delta = 0

                    user.used = int(
                        user.used or 0
                    ) + delta

                    set_last_usage(
                        db,
                        user.uuid,
                        node.id,
                        used_bytes,
                    )

                    logger.info(
                        f"[MULTINODE-USAGE] "
                        f"user={clean_username}, "
                        f"node={node.name}, "
                        f"last={last_usage}, "
                        f"current={used_bytes}, "
                        f"delta={delta}, "
                        f"shared_total={user.used}"
                    )

                db.commit()

                logger.info(
                    f"Traffic committed for "
                    f"node {node.name}"
                )

            except Exception as e:
                db.rollback()

                logger.error(
                    f"Error while processing node "
                    f"{node.address} -> {e}",
                    exc_info=True,
                )

    except Exception as e:
        db.rollback()

        logger.error(
            f"Error in check_user_used_traffic -> {e}",
            exc_info=True,
        )

    finally:
        db.close()


# MULTINODE_RESET_BASELINE_V1
async def reset_shared_user_usage(user, db):
    """
    Baseline the current OpenVPN counter on every assigned
    node, then reset the shared user.used value.

    This prevents pre-reset traffic from being counted again
    on the next MultiNode usage-sync cycle.
    """

    ensure_usage_table(db)

    baselines = []

    for node in crud.get_all_nodes(db):
        if not user_can_access_node(
            db,
            user.uuid,
            node.id,
        ):
            continue

        client_name = f"{user.name}-{node.name}"

        try:
            usage_map = await get_users_used_traffic(
                node,
                db=db,
            )
        except Exception:
            logger.exception(
                f"[MULTINODE-RESET] "
                f"could not read node={node.name}"
            )
            raise RuntimeError(
                f"Cannot baseline node {node.name}"
            )

        if not usage_map:
            logger.info(
                f"[MULTINODE-RESET] "
                f"no usage returned by node={node.name}; "
                f"keeping previous baseline"
            )
            continue

        if client_name not in usage_map:
            logger.info(
                f"[MULTINODE-RESET] "
                f"client={client_name} not present on "
                f"node={node.name}; keeping previous baseline"
            )
            continue

        try:
            current = int(
                usage_map.get(client_name) or 0
            )
        except (TypeError, ValueError):
            raise RuntimeError(
                f"Invalid usage counter on node {node.name}"
            )

        baselines.append(
            (node.id, node.name, current)
        )

    # Apply baselines only after successful collection.
    for node_id, node_name, current in baselines:
        set_last_usage(
            db,
            user.uuid,
            node_id,
            current,
        )

        logger.info(
            f"[MULTINODE-RESET] "
            f"user={user.name}, "
            f"node={node_name}, "
            f"baseline={current}"
        )

    user.used = 0
    user.last_node_usage = 0

    db.commit()
    db.refresh(user)

    logger.info(
        f"[MULTINODE-RESET] "
        f"user={user.name}, "
        f"shared_used=0, "
        f"nodes_baselined={len(baselines)}"
    )

    return len(baselines)

