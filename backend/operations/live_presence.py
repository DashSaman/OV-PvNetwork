from __future__ import annotations

import asyncio
import copy
import time
from typing import Iterable

from sqlalchemy import func

from backend.db.engine import SessionLocal
from backend.db.models import ActiveSession, Node, User
from backend.logger import logger
from backend.node.requests import NodeRequests

CENTRAL_SESSION_TTL_SECONDS = 90
DIRECT_CACHE_TTL_SECONDS = 4.0
DIRECT_STALE_GRACE_SECONDS = 30.0
PRESENCE_SNAPSHOT_TTL_SECONDS = 3.0

_direct_cache: dict[int, dict] = {}
_cache_lock: asyncio.Lock | None = None
_cache_lock_loop = None
_presence_cache: dict[str, object] = {}
_presence_lock: asyncio.Lock | None = None
_presence_lock_loop = None


def _get_cache_lock() -> asyncio.Lock:
    global _cache_lock, _cache_lock_loop
    loop = asyncio.get_running_loop()
    if _cache_lock is None or _cache_lock_loop is not loop:
        _cache_lock = asyncio.Lock()
        _cache_lock_loop = loop
    return _cache_lock


def _get_presence_lock() -> asyncio.Lock:
    global _presence_lock, _presence_lock_loop
    loop = asyncio.get_running_loop()
    if _presence_lock is None or _presence_lock_loop is not loop:
        _presence_lock = asyncio.Lock()
        _presence_lock_loop = loop
    return _presence_lock


def client_username(client_name: str, node_name: str) -> str | None:
    client = str(client_name or "")
    node = str(node_name or "")
    suffix = f"-{node}"
    if not client or not node or not client.casefold().endswith(suffix.casefold()):
        return None
    username = client[: len(client) - len(suffix)]
    return username or None


def merge_presence_snapshot(
    *,
    users: Iterable[tuple[str, str]],
    central_counts: dict[str, int],
    node_clients: dict[int, tuple[str, set[str]]],
) -> dict:
    identities = [(str(uuid), str(name)) for uuid, name in users]
    known_uuids = {uuid for uuid, _ in identities}
    by_name = {name.casefold(): uuid for uuid, name in identities if name}
    counts = {
        str(uuid): max(0, int(count))
        for uuid, count in central_counts.items()
        if str(uuid) in known_uuids and int(count) > 0
    }
    direct_nodes_by_uuid: dict[str, set[int]] = {}
    managed_uuids_by_node: dict[int, set[str]] = {}
    unmapped_by_node: dict[int, int] = {}
    unmapped_clients = 0

    for raw_node_id, value in node_clients.items():
        node_id = int(raw_node_id)
        node_name, clients = value
        managed_uuids_by_node.setdefault(node_id, set())
        unmapped_by_node.setdefault(node_id, 0)
        for client_name in clients:
            username = client_username(client_name, node_name)
            if not username:
                unmapped_clients += 1
                unmapped_by_node[node_id] += 1
                continue
            user_uuid = by_name.get(username.casefold())
            if not user_uuid:
                unmapped_clients += 1
                unmapped_by_node[node_id] += 1
                continue
            direct_nodes_by_uuid.setdefault(user_uuid, set()).add(node_id)
            managed_uuids_by_node[node_id].add(user_uuid)

    direct_fallback_users = 0
    for user_uuid, node_ids in direct_nodes_by_uuid.items():
        direct_count = len(node_ids)
        central_count = counts.get(user_uuid, 0)
        if central_count <= 0:
            direct_fallback_users += 1
        counts[user_uuid] = max(central_count, direct_count)

    return {
        "counts_by_uuid": counts,
        "online_users": sum(1 for count in counts.values() if count > 0),
        "central_online_users": sum(
            1
            for uuid, count in central_counts.items()
            if str(uuid) in known_uuids and int(count) > 0
        ),
        "direct_fallback_users": direct_fallback_users,
        "managed_online_by_node": {
            node_id: len(user_uuids)
            for node_id, user_uuids in managed_uuids_by_node.items()
        },
        "unmapped_clients": unmapped_clients,
        "unmapped_clients_by_node": unmapped_by_node,
    }


def _db_snapshot() -> tuple[list[tuple[str, str]], dict[str, int], list[dict]]:
    cutoff = int(time.time()) - CENTRAL_SESSION_TTL_SECONDS
    with SessionLocal() as db:
        users = [
            (str(uuid), str(name))
            for uuid, name in db.query(User.uuid, User.name).all()
        ]
        central_counts = {
            str(uuid): int(count)
            for uuid, count in (
                db.query(
                    ActiveSession.user_uuid,
                    func.count(ActiveSession.session_id),
                )
                .filter(ActiveSession.last_seen >= cutoff)
                .group_by(ActiveSession.user_uuid)
                .all()
            )
        }
        node_specs = [
            {
                "id": int(node.id),
                "name": str(node.name),
                "address": str(node.address),
                "port": int(node.port),
                "key": str(node.key),
                "tunnel_address": str(node.tunnel_address or node.address),
                "protocol": str(node.protocol or "udp"),
                "ovpn_port": int(node.ovpn_port or 1194),
            }
            for node in (
                db.query(Node)
                .filter(Node.status.is_(True))
                .order_by(Node.id)
                .all()
            )
        ]
    return users, central_counts, node_specs


def _read_node_clients(spec: dict) -> set[str] | None:
    request = NodeRequests(
        address=spec["address"],
        port=spec["port"],
        api_key=spec["key"],
        tunnel_address=spec["tunnel_address"],
        protocol=spec["protocol"],
        ovpn_port=spec["ovpn_port"],
        set_new_setting=False,
    )
    data = request.get_users_usage(timeout=(1.0, 2.5))
    normal_clients: set[str] = set()
    if isinstance(data, dict):
        users = data.get("users")
        if isinstance(users, dict):
            normal_clients = {str(client_name) for client_name in users.keys()}

    router_clients: set[str] = set()
    router_status = request.router_openvpn_status()
    if isinstance(router_status, dict) and router_status.get("ok"):
        router_data = router_status.get("data")
        if isinstance(router_data, dict):
            common_names = router_data.get("online_common_names")
            if isinstance(common_names, list):
                router_clients = {
                    str(item) for item in common_names if str(item or "").strip()
                }

    # Node `/sync/usage` returns data=null when it successfully sampled zero
    # normal OpenVPN clients.  That is a fresh empty snapshot, not a poll
    # failure.  Actual request/application failures are returned as False.
    normal_snapshot_known = data is None or isinstance(data, dict)
    if not normal_snapshot_known and not router_clients:
        return None
    return normal_clients | router_clients


async def _collect_direct_clients(node_specs: list[dict]) -> tuple[dict, list[int]]:
    now = time.monotonic()
    current_ids = {int(spec["id"]) for spec in node_specs}

    async with _get_cache_lock():
        for node_id in list(_direct_cache):
            if node_id not in current_ids:
                _direct_cache.pop(node_id, None)

        stale_specs = []
        result: dict[int, tuple[str, set[str]]] = {}
        failed: list[int] = []

        for spec in node_specs:
            node_id = int(spec["id"])
            cached = _direct_cache.get(node_id)
            if (
                cached
                and cached.get("name") == spec["name"]
                and now - float(cached.get("at", 0.0)) < DIRECT_CACHE_TTL_SECONDS
            ):
                result[node_id] = (spec["name"], set(cached.get("clients", set())))
            else:
                stale_specs.append(spec)

        if stale_specs:
            polled = await asyncio.gather(
                *[asyncio.to_thread(_read_node_clients, spec) for spec in stale_specs],
                return_exceptions=True,
            )
            sample_time = time.monotonic()
            for spec, clients in zip(stale_specs, polled):
                node_id = int(spec["id"])
                if isinstance(clients, set):
                    _direct_cache[node_id] = {
                        "at": sample_time,
                        "name": spec["name"],
                        "clients": set(clients),
                    }
                    result[node_id] = (spec["name"], set(clients))
                    continue

                failed.append(node_id)
                cached = _direct_cache.get(node_id)
                if (
                    cached
                    and cached.get("name") == spec["name"]
                    and sample_time - float(cached.get("at", 0.0))
                    < DIRECT_STALE_GRACE_SECONDS
                ):
                    result[node_id] = (
                        spec["name"],
                        set(cached.get("clients", set())),
                    )

        return result, failed


async def get_display_live_presence() -> dict:
    """Return one shared display snapshot without mutating enforcement sessions."""
    now = time.monotonic()
    cached = _presence_cache.get("data")
    cached_at = float(_presence_cache.get("at") or 0.0)
    if isinstance(cached, dict) and now - cached_at < PRESENCE_SNAPSHOT_TTL_SECONDS:
        return copy.deepcopy(cached)

    async with _get_presence_lock():
        now = time.monotonic()
        cached = _presence_cache.get("data")
        cached_at = float(_presence_cache.get("at") or 0.0)
        if isinstance(cached, dict) and now - cached_at < PRESENCE_SNAPSHOT_TTL_SECONDS:
            return copy.deepcopy(cached)

        users, central_counts, node_specs = _db_snapshot()
        try:
            node_clients, failed_node_ids = await _collect_direct_clients(node_specs)
        except Exception as exc:
            logger.warning("Display live-presence node fallback failed: %s", type(exc).__name__)
            node_clients, failed_node_ids = {}, [int(spec["id"]) for spec in node_specs]

        result = merge_presence_snapshot(
            users=users,
            central_counts=central_counts,
            node_clients=node_clients,
        )
        result.update(
            {
                "failed_node_ids": sorted(failed_node_ids),
                "sample_time": int(time.time()),
            }
        )
        _presence_cache["at"] = time.monotonic()
        _presence_cache["data"] = copy.deepcopy(result)
        return copy.deepcopy(result)
