from __future__ import annotations

import asyncio
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db import crud
from backend.node.requests import NodeRequests


HEALTHY_CPU_LIMIT = 85.0
HEALTHY_MEMORY_LIMIT = 90.0
DEGRADED_LATENCY_MS = 1500.0

SESSION_TTL_SECONDS = 90


def _as_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)

    except (TypeError, ValueError):
        return default


def _as_int(
    value: Any,
    default: int = 0,
) -> int:

    try:
        return int(value)

    except (TypeError, ValueError):
        return default


def decorate_node_list(
    db: Session,
    items,
):

    db_nodes = {
        int(node.id): node
        for node in crud.get_all_nodes(db)
    }

    result = []

    for raw in items or []:

        if isinstance(raw, dict):
            item = dict(raw)
        else:
            try:
                item = dict(raw)
            except Exception:
                result.append(raw)
                continue


        node_id = item.get("id")

        try:
            node_id = int(node_id)
        except (TypeError, ValueError):
            result.append(item)
            continue


        node = db_nodes.get(node_id)

        if node is None:
            result.append(item)
            continue


        item["enabled"] = bool(
            node.status
        )

        item["drain"] = bool(
            getattr(
                node,
                "drain",
                False,
            )
        )

        item["weight"] = int(
            getattr(
                node,
                "weight",
                100,
            )
            or 0
        )

        result.append(item)


    return result


def update_node_control(
    db: Session,
    node_id: int,
    drain=None,
    weight=None,
):

    node = crud.get_node_by_id(
        db,
        node_id,
    )

    if node is None:
        raise ValueError(
            "Node not found"
        )


    if drain is not None:
        node.drain = bool(drain)


    if weight is not None:

        weight = int(weight)

        if (
            weight < 0
            or weight > 1000
        ):
            raise ValueError(
                "Weight must be between 0 and 1000"
            )

        node.weight = weight


    db.commit()
    db.refresh(node)


    return {
        "id": int(node.id),
        "name": str(node.name),
        "enabled": bool(node.status),
        "drain": bool(node.drain),
        "weight": int(node.weight),
    }


def _central_session_counts(
    db: Session,
):

    cutoff = (
        int(time.time())
        - SESSION_TTL_SECONDS
    )


    rows = db.execute(
        text(
            """
            SELECT
                node_id,
                COUNT(session_id)
                    AS active_sessions,
                COUNT(DISTINCT user_uuid)
                    AS online_users
            FROM active_sessions
            WHERE last_seen >= :cutoff
            GROUP BY node_id
            """
        ),
        {
            "cutoff": cutoff,
        },
    ).mappings().all()


    return {
        int(row["node_id"]): {
            "active_sessions":
                int(
                    row["active_sessions"]
                    or 0
                ),

            "online_users":
                int(
                    row["online_users"]
                    or 0
                ),
        }

        for row in rows
    }


async def _probe_node(
    node,
    central_counts,
):

    enabled = bool(node.status)

    drain = bool(
        getattr(
            node,
            "drain",
            False,
        )
    )

    weight = int(
        getattr(
            node,
            "weight",
            100,
        )
        or 0
    )


    base = {
        "id": int(node.id),
        "name": str(node.name),
        "address": str(node.address),
        "api_port": int(node.port),
        "protocol": str(node.protocol),
        "ovpn_port": int(node.ovpn_port),
        "enabled": enabled,
        "drain": drain,
        "weight": weight,

        "central_online_users":
            central_counts.get(
                int(node.id),
                {},
            ).get(
                "online_users",
                0,
            ),

        "central_active_sessions":
            central_counts.get(
                int(node.id),
                {},
            ).get(
                "active_sessions",
                0,
            ),

        "checked_at":
            int(time.time()),
    }


    if not enabled:

        return {
            **base,

            "health":
                "disabled",

            "health_reason":
                ["admin_disabled"],

            "eligible_for_new_connections":
                False,

            "api_latency_ms":
                None,

            "cpu_usage":
                None,

            "memory_usage":
                None,

            "reported_online_users":
                0,

            "reported_online_sessions":
                0,

            "selection_score":
                None,
        }


    started = time.monotonic()

    try:

        info = await asyncio.to_thread(
            NodeRequests(
                address=node.address,
                port=node.port,
                api_key=node.key,

                tunnel_address=(
                    node.tunnel_address
                    or ""
                ),

                protocol=node.protocol,
                ovpn_port=node.ovpn_port,

                set_new_setting=False,
            ).get_node_info
        )

    except Exception:
        info = None


    latency_ms = round(
        (
            time.monotonic()
            - started
        )
        * 1000,
        1,
    )


    if (
        not isinstance(info, dict)
        or info.get("status")
        != "running"
    ):

        return {
            **base,

            "health":
                "offline",

            "health_reason":
                ["node_api_unreachable"],

            "eligible_for_new_connections":
                False,

            "api_latency_ms":
                latency_ms,

            "cpu_usage":
                None,

            "memory_usage":
                None,

            "reported_online_users":
                0,

            "reported_online_sessions":
                0,

            "selection_score":
                None,
        }


    cpu = _as_float(
        info.get(
            "cpu_usage"
        )
    )

    memory = _as_float(
        info.get(
            "memory_usage"
        )
    )

    reported_users = _as_int(
        info.get(
            "online_count"
        )
    )

    reported_sessions = _as_int(
        info.get(
            "online_sessions"
        )
    )


    reasons = []

    if cpu >= HEALTHY_CPU_LIMIT:
        reasons.append(
            "high_cpu"
        )

    if memory >= HEALTHY_MEMORY_LIMIT:
        reasons.append(
            "high_memory"
        )

    if latency_ms >= DEGRADED_LATENCY_MS:
        reasons.append(
            "high_api_latency"
        )


    health = (
        "degraded"
        if reasons
        else "healthy"
    )


    eligible = (
        enabled
        and not drain
        and health
        in {
            "healthy",
            "degraded",
        }
    )


    effective_sessions = max(
        reported_sessions,
        int(
            base[
                "central_active_sessions"
            ]
        ),
    )


    score = None

    if eligible:

        #
        # Higher score is better.
        #
        # API latency is only a health/control-plane
        # signal. It is NOT treated as user geographic
        # latency.
        #
        score = round(
            (
                weight * 10.0
            )
            - (
                cpu * 2.0
            )
            - (
                memory * 1.5
            )
            - min(
                latency_ms,
                2000.0,
            ) * 0.10
            - (
                effective_sessions
                * 10.0
            ),
            2,
        )


    return {
        **base,

        "health":
            health,

        "health_reason":
            reasons,

        "administrative_state":
            (
                "draining"
                if drain
                else "enabled"
            ),

        "eligible_for_new_connections":
            eligible,

        "api_latency_ms":
            latency_ms,

        "cpu_usage":
            cpu,

        "memory_usage":
            memory,

        "reported_online_users":
            reported_users,

        "reported_online_sessions":
            reported_sessions,

        "selection_score":
            score,

        "uptime":
            _as_int(
                info.get(
                    "uptime"
                )
            ),

        "traffic_bytes":
            _as_int(
                info.get(
                    "traffic_bytes"
                )
            ),
    }


async def build_nodes_health(
    db: Session,
):

    nodes = crud.get_all_nodes(db)

    counts = _central_session_counts(
        db
    )


    results = await asyncio.gather(
        *[
            _probe_node(
                node,
                counts,
            )
            for node in nodes
        ]
    )


    def sort_key(item):

        health_rank = {
            "healthy": 0,
            "degraded": 1,
            "offline": 2,
            "disabled": 3,
        }.get(
            item.get(
                "health"
            ),
            9,
        )


        return (
            0
            if item.get(
                "eligible_for_new_connections"
            )
            else 1,

            health_rank,

            -(
                item.get(
                    "selection_score"
                )
                or -100000
            ),
        )


    results.sort(
        key=sort_key
    )


    recommendation_set = False

    for item in results:

        recommended = False

        if (
            not recommendation_set
            and item.get(
                "eligible_for_new_connections"
            )
        ):

            recommended = True
            recommendation_set = True


        item["recommended"] = (
            recommended
        )


    return results
