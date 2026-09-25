"""PVN-1016/PVN-1017 — per-user live traffic rates from node counters.

/sync/usage on each node reports cumulative rx/tx bytes per Common Name
(``{username}-{node_name}``). Nodes patched with
``PVNETWORK_USERS_RX_TX_SPLIT_V1`` additionally report ``users_rx`` /
``users_tx`` so download and upload rates are computed separately; on
legacy nodes only the combined ``users`` total is available.
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
    if isinstance(data, dict) and isinstance(data.get("users"), dict):
        return data
    return None


def _accumulate(target: dict, username: str, value) -> None:
    try:
        target[username] = target.get(username, 0.0) + float(value or 0.0)
    except (TypeError, ValueError):
        pass


async def _sample_all() -> dict:
    """Fetch per-CN cumulative bytes (total / rx / tx) from every enabled node."""
    loop = asyncio.get_running_loop()
    db = sessionLocal()
    try:
        nodes = db.query(Node).filter(Node.status.is_(True)).all()
        specs = [
            (
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
    finally:
        db.close()

    async def one(node_name: str, client: NodeRequests):
        try:
            payload = await loop.run_in_executor(None, _fetch_usage, client)
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            return None
        totals: dict[str, float] = {}
        rx_map: dict[str, float] = {}
        tx_map: dict[str, float] = {}
        users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
        users_rx = payload.get("users_rx") if isinstance(payload.get("users_rx"), dict) else {}
        users_tx = payload.get("users_tx") if isinstance(payload.get("users_tx"), dict) else {}
        for client_name, value in users.items():
            username = client_username(client_name, node_name)
            if username:
                _accumulate(totals, username, value)
        for client_name, value in users_rx.items():
            username = client_username(client_name, node_name)
            if username:
                _accumulate(rx_map, username, value)
        for client_name, value in users_tx.items():
            username = client_username(client_name, node_name)
            if username:
                _accumulate(tx_map, username, value)
        return totals, rx_map, tx_map

    results = await asyncio.gather(
        *(one(name, client) for name, client in specs),
        return_exceptions=True,
    )

    combined: dict[str, float] = {}
    rx_all: dict[str, float] = {}
    tx_all: dict[str, float] = {}
    for result in results:
        if not isinstance(result, tuple):
            continue
        totals, rx_map, tx_map = result
        for username, value in totals.items():
            combined[username] = combined.get(username, 0.0) + value
        for username, value in rx_map.items():
            rx_all[username] = rx_all.get(username, 0.0) + value
        for username, value in tx_map.items():
            tx_all[username] = tx_all.get(username, 0.0) + value
    return {"total": combined, "rx": rx_all, "tx": tx_all}


def _uuid_map() -> dict[str, str]:
    db = sessionLocal()
    try:
        return {str(name): str(uuid) for uuid, name in db.query(User.uuid, User.name).all()}
    finally:
        db.close()


async def get_user_live_rates() -> dict:
    """Return per-uuid live rates in bits/s.

    ``{"rates_bps_by_uuid": {uuid: {"down": bps, "up": bps, "total": bps}}}``.
    Legacy rows (combined only) keep down=up=0 with total filled.
    """
    now = time.monotonic()
    async with _lock:
        cached = _cache.get("data")
        if cached is not None and now - float(_cache.get("time") or 0.0) < _CACHE_TTL:
            return cached

        current = await _sample_all()
        now_real = time.time()
        prev = _prev.get("bytes") or {}
        elapsed = now_real - float(_prev.get("time") or 0.0)

        def delta(which: str) -> dict[str, float]:
            out: dict[str, float] = {}
            prev_map = prev.get(which) or {}
            for username, value in current.get(which, {}).items():
                before = prev_map.get(username)
                if before is not None and value >= before:
                    out[username] = (value - before) / elapsed
            return out

        rates_total: dict[str, float] = {}
        rates_rx: dict[str, float] = {}
        rates_tx: dict[str, float] = {}
        if prev and 0.4 <= elapsed <= 30.0:
            rates_total = delta("total")
            rates_rx = delta("rx")
            rates_tx = delta("tx")

        try:
            mapping = await asyncio.get_running_loop().run_in_executor(None, _uuid_map)
        except Exception:
            mapping = {}

        by_uuid: dict[str, dict] = {}
        for username, total_bps in rates_total.items():
            uuid = mapping.get(username)
            if not uuid or total_bps <= 0:
                continue
            down = rates_rx.get(username, 0.0)
            up = rates_tx.get(username, 0.0)
            by_uuid[uuid] = {
                "down": round(down * 8, 1),
                "up": round(up * 8, 1),
                "total": round(total_bps * 8, 1),
            }

        payload = {"rates_bps_by_uuid": by_uuid, "sample_time": int(now_real)}
        _cache["data"] = payload
        _cache["time"] = time.monotonic()
        if current.get("total"):
            _prev["bytes"] = current
            _prev["time"] = now_real
        return payload
