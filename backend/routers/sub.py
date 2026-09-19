import time
import asyncio
from fastapi import (
    APIRouter,
    Depends,
    Request,
    HTTPException,
)
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.config import config
from backend.db.engine import get_db
from backend.db import crud
from backend.routers.anyconnect import subscription_anyconnect_details
from backend.node.assignment import (
    get_user_nodes,
    user_can_access_node,
)
from backend.node.task import (
    download_ovpn_client_from_node,
)
from backend.node.requests import NodeRequests


templates = Jinja2Templates(
    directory="frontend/templates"
)

router = APIRouter(
    prefix=f"/{config.SUBSCRIPTION_PATH}",
    tags=["Subscription"],
)


# OV_SUB_PRIVATE_NETWORK_V3
@router.get("/{uuid}")
async def get_subscription(
    request: Request,
    uuid: str,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_uuid(db, uuid)
    if not user:
        raise HTTPException(status_code=404)

    user_data = {
        "name": user.name,
        "expiry_date": user.expiry_date,
        "total": user.total,
        "used": user.used,
        "is_active": user.is_active,
        "device_limit": int(user.device_limit or 0),
    }

    anyconnect = subscription_anyconnect_details(
        db,
        user.uuid,
        user.name,
    )

    nodes = get_user_nodes(
        db,
        user.uuid,
        active_only=False,
    )

    flags = {
        "Finland": "🇫🇮",
        "USA": "🇺🇸",
        "Germany": "🇩🇪",
        "Turkey": "🇹🇷",
    }

    specs = []
    for node in nodes:
        specs.append(
            {
                "name": str(node.name),
                "address": str(node.address),
                "port": int(node.port),
                "key": str(node.key),
                "enabled": bool(node.status),
                "drain": bool(getattr(node, "drain", False)),
                "maintenance": bool(getattr(node, "maintenance", False)),
                "tunnel_address": str(
                    getattr(node, "tunnel_address", None)
                    or "pvnetwork.example"
                ),
                "protocol": str(
                    getattr(node, "protocol", None)
                    or "udp"
                ),
                "ovpn_port": int(
                    getattr(node, "ovpn_port", None)
                    or 1194
                ),
            }
        )

    db.close()

    async def read_node(spec):
        if (
            not spec["enabled"]
            or spec["drain"]
            or spec["maintenance"]
        ):
            return {}

        def worker():
            return NodeRequests(
                address=spec["address"],
                port=spec["port"],
                api_key=spec["key"],
                tunnel_address=spec["tunnel_address"],
                protocol=spec["protocol"],
                ovpn_port=spec["ovpn_port"],
                set_new_setting=False,
            ).get_node_info()

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(worker),
                timeout=4.0,
            )
        except Exception:
            return {}

    t1 = time.monotonic()
    first_results = await asyncio.gather(
        *[read_node(spec) for spec in specs]
    )
    first_by_name = {
        spec["name"]: result
        for spec, result in zip(specs, first_results)
    }

    reachable_specs = []
    for spec in specs:
        info = first_by_name.get(spec["name"]) or {}
        if (
            isinstance(info, dict)
            and info.get("status") == "running"
        ):
            reachable_specs.append(spec)

    await asyncio.sleep(1.0)

    second_results = await asyncio.gather(
        *[read_node(spec) for spec in reachable_specs]
    )
    second_by_name = {
        spec["name"]: result
        for spec, result in zip(
            reachable_specs,
            second_results,
        )
    }

    t2 = time.monotonic()
    elapsed = max(0.5, t2 - t1)

    node_items = []

    for spec in specs:
        base = {
            "name": spec["name"],
            "flag": flags.get(spec["name"], "🌐"),
            "online": False,
            "mbps": 0.0,
            "rx_mbps": 0.0,
            "tx_mbps": 0.0,
            "load": 0,
            "state": "offline",
            "state_fa": "آفلاین",
            "recommended": False,
        }

        if (
            not spec["enabled"]
            or spec["drain"]
            or spec["maintenance"]
        ):
            node_items.append(base)
            continue

        a = first_by_name.get(spec["name"]) or {}
        b = second_by_name.get(spec["name"]) or {}

        if (
            not isinstance(a, dict)
            or not isinstance(b, dict)
            or a.get("status") != "running"
            or b.get("status") != "running"
        ):
            node_items.append(base)
            continue

        try:
            rx1 = int(a.get("rx_bytes", 0) or 0)
            tx1 = int(a.get("tx_bytes", 0) or 0)
            rx2 = int(b.get("rx_bytes", 0) or 0)
            tx2 = int(b.get("tx_bytes", 0) or 0)
        except Exception:
            node_items.append(base)
            continue

        if rx2 < rx1 or tx2 < tx1:
            node_items.append(base)
            continue

        rx_mbps = (
            (rx2 - rx1) * 8 / elapsed / 1_000_000
        )
        tx_mbps = (
            (tx2 - tx1) * 8 / elapsed / 1_000_000
        )
        total_mbps = max(0.0, rx_mbps + tx_mbps)

        base.update(
            {
                "online": True,
                "mbps": round(total_mbps, 1),
                "rx_mbps": round(rx_mbps, 1),
                "tx_mbps": round(tx_mbps, 1),
            }
        )
        node_items.append(base)

    online_items = [
        item for item in node_items
        if item["online"]
    ]
    # OV_PVNETWORK_ABSOLUTE_LOAD_V2
    # Subscription is sampled once while the page is rendered.
    # 100 Mbps is the absolute visual reference.
    for item in online_items:
        mbps = max(
            0.0,
            float(
                item.get("mbps", 0)
                or 0
            ),
        )

        item["load"] = max(
            0,
            min(
                100,
                int(round(mbps)),
            ),
        )

        if mbps < 30:
            item["state"] = "low"
            item["state_fa"] = "خلوت"

        elif mbps <= 100:
            item["state"] = "normal"
            item["state_fa"] = "نیمه‌خلوت"

        else:
            item["state"] = "busy"
            item["state_fa"] = "شلوغ"


    if online_items:
        recommended = min(
            online_items,
            key=lambda item: (
                item["mbps"],
                item["name"],
            ),
        )
        recommended["recommended"] = True

    node_items.sort(
        key=lambda item: (
            not item["recommended"],
            not item["online"],
            item["load"],
            item["name"],
        )
    )

    ovpn_download_links = {}
    node_health = {}

    for item in node_items:
        name = item["name"]
        node_health[name] = item
        if item["online"]:
            ovpn_download_links[name] = (
                f"{request.base_url}"
                f"{config.SUBSCRIPTION_PATH}"
                f"/download/{uuid}/{name}"
            )

    return templates.TemplateResponse(
        "subscription.html",
        {
            "request": request,
            **user_data,
            "ovpn_download_links": ovpn_download_links,
            "node_health": node_health,
            "anyconnect": anyconnect,
        },
    )

@router.get("/download/{uuid}/{node_name}")
async def download_ovpn(
    uuid: str,
    node_name: str,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_uuid(
        db,
        uuid,
    )

    if not user:
        raise HTTPException(status_code=404)

    node_obj = crud.get_node_by_name(
        db,
        node_name,
    )

    if not node_obj or not node_obj.status:
        raise HTTPException(status_code=404)

    if not user_can_access_node(
        db,
        user.uuid,
        node_obj.id,
    ):
        raise HTTPException(
            status_code=404,
            detail="Node is not assigned to this user",
        )

    response = await download_ovpn_client_from_node(
        user.uuid,
        node_obj.id,
        db,
    )

    if not response:
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    return response
