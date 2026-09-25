"""PVN-1016 — per-user live traffic rates from node cumulative counters.

/sync/usage on each node reports cumulative rx+tx bytes per Common Name
(``{username}-{node_name}``). Sampling that twice yields a per-user bit rate,
exactly like the dashboard computes global totals. Results are cached for a
short window so the 1-second Users-page presence polling never hammers nodes.
"""
from __future__ import annotations

import asyncio
import time

from backend.db.engine import sessionLocal
from backend.db.models import Node, User
from backend.node.requests import NodeRequests
from backend.operations.live_presence import client_username

_CACHE_TTL = 1.6
_lock = asyncio.Lock()
_cache: dict = {"data": None, "time": 0.0}
_prev: dict = {"bytes": {}, "time": 0.0}


def _fetch_usage(client: NodeRequests) -> dict | None:
    data = client.get_users_usage()
    if isinstance(data, dict):
        usage = data.get("users")
        if isinstance(usage, dict):
            return usage
    return None


async def _sample_all() -> dict:
    """Fetch per-CN cumulative bytes from every enabled node in parallel."""
    loop = asyncio.get_running_loop()
    db = sessionLocal()
    try:
        nodes = (
            db.query(Node)
            .filter(Node.status.is_(True))
            .all()
        )
        specs = [
            (
                int(n.id),
                str(n.name),
                NodeRequests(
                    address=str(n.address),
                    port=int(n.port),
                    api_key=str(n.key),
                    tunnel_address=str(n.tunnel_address or n.address),
                ),
            )
            for n in nodes
        ]
        names_by_id = {str(n.name): str(n.name) for n in nodes}
    finally:
        db.close()

    async def one(node_id: int, node_name: str, client: NodeRequests):
        try:
            usage = await loop.run_in_executor(None, _fetch_usage, client)
        except Exception:
            usage = None
        if not isinstance(usage, dict):
            return {}
        out: dict[str, float] = {}
        for client_name, value in usage.items():
            username = client_username(client_name, node_name)
            if not username:
                continue
            try:
                out[username] = out.get(username, 0.0) + float(value or 0.0)
            except (TypeError, ValueError):
                continue
        return out

    results = await asyncio.gather(
        *(one(node_id, name, client) for node_id, name, client in specs),
        return_exceptions=True,
    )

    combined: dict[str, float] = {}
    for result in results:
        if isinstance(result, dict):
            for username, value in result.items():
                combined[username] = combined.get(username, 0.0) + value
    _ = names_by_id
    return combined


def _uuid_map() -> dict[str, str]:
    db = sessionLocal()
    try:
        return {str(name): str(uuid) for uuid, name in db.query(User.uuid, User.name).all()}
    finally:
        db.close()


async def get_user_live_rates() -> dict:
    """Return ``{"rates_bps_by_uuid": {uuid: bps}, "sample_time": epoch}``.

    Rates are bytes-per-second of rx+tx summed across nodes; a fresh sample
    that cannot compute a delta (first run) yields an empty rate map.
    """
    now = time.monotonic()
    async with _lock:
        cached = _cache.get("data")
        if cached is not None and now - float(_cache.get("time") or 0.0) < _CACHE_TTL:
            return cached

        current = await _sample_all()
        now_real = time.time()
        rates_by_name: dict[str, float] = {}
        prev_bytes = _prev.get("bytes") or {}
        elapsed = now_real - float(_prev.get("time") or 0.0)
        if prev_bytes and 0.4 <= elapsed <= 30.0:
            for username, value in current.items():
                before = prev_bytes.get(username)
                if before is not None and value >= before:
                    rates_by_name[username] = (value - before) / elapsed

        by_uuid: dict[str, float] = {}
        try:
            mapping = await asyncio.get_running_loop().run_in_executor(
                None, _uuid_map
            )
        except Exception:
            mapping = {}
        for username, rate in rates_by_name.items():
            uuid = mapping.get(username)
            if uuid and rate > 0:
                by_uuid[uuid] = round(rate * 8, 1)  # bits/s for the UI

        payload = {"rates_bps_by_uuid": by_uuid, "sample_time": int(now_real)}
        _cache["data"] = payload
        _cache["time"] = time.monotonic()
        if current:
            _prev["bytes"] = current
            _prev["time"] = now_real
        return payload
