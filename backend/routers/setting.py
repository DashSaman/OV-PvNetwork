from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.db.engine import get_db
from backend.db import crud
from backend.auth.auth import get_current_user
from backend.operations.server_info import get_server_info
from backend.schema.output import Settings, ServerInfo, ResponseModel
from backend.config import config

router = APIRouter(prefix="/server", tags=["Panel Settings"])


@router.get("/settings", response_model=ResponseModel)
async def get_settings(
    request: Request,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    settings = Settings(
        subscription_path=config.SUBSCRIPTION_PATH,
        subscription_url_prefix=(
            config.SUBSCRIPTION_URL_PREFIX + "/"
            if config.SUBSCRIPTION_URL_PREFIX is not None
            else str(request.base_url)
        ),
    )
    return ResponseModel(
        success=True,
        msg="Settings retrieved successfully",
        data=settings,
    )


@router.get(
    "/info",
    response_model=ResponseModel,
    description="Get server information (cpu, memory, ...)",
)
async def get_server_information(user: dict = Depends(get_current_user)):
    result = await get_server_info()
    return ResponseModel(
        success=True,
        msg="Server information retrieved successfully",
        data=ServerInfo.from_orm(result),
    )


# ============================================================
# OV_DASHBOARD_AGGREGATOR_V1
#
# One dashboard request -> four concurrent node status calls.
#
# IMPORTANT:
# - DB session is closed BEFORE any network request.
# - Node HTTP requests run in worker threads.
# - 4 second in-process cache prevents unnecessary fan-out.
# ============================================================

_dashboard_live_cache = {
    "time": 0.0,
    "data": None,
}


# OV_DASHBOARD_SERVER_RATE_V2
#
# Rate calculation lives on the panel backend.
# Each node gets its OWN sample timestamp.
# Browser timing and slow sibling nodes cannot distort Mbps.
_dashboard_rate_state = {}


@router.get("/dashboard-live")
async def get_dashboard_live(
    user: dict = Depends(get_current_user),
):
    import asyncio
    import time

    from backend.db.engine import sessionLocal
    from backend.db.models import Node
    from backend.node.requests import NodeRequests

    now = time.monotonic()

    cached = _dashboard_live_cache.get("data")
    cached_at = float(
        _dashboard_live_cache.get("time") or 0
    )

    if (
        cached is not None
        and now - cached_at < 0.90
    ):
        return {
            "success": True,
            "msg": "Dashboard live metrics retrieved",
            "data": cached,
        }

    db = sessionLocal()

    try:
        rows = (
            db.query(Node)
            .order_by(Node.id)
            .all()
        )

        node_specs = [
            {
                "id": int(node.id),
                "name": str(node.name),
                "address": str(node.address),
                "port": int(node.port),
                "key": str(node.key),
                "tunnel_address": (
                    str(node.tunnel_address)
                    if node.tunnel_address
                    else str(node.address)
                ),
                "protocol": str(node.protocol),
                "ovpn_port": int(node.ovpn_port),
                "enabled": bool(node.status),
            }
            for node in rows
        ]

    finally:
        # Critical:
        # Never hold a SQLAlchemy connection while
        # waiting for another server over HTTP.
        db.close()

    def read_node(spec: dict) -> dict:
        if not spec["enabled"]:
            return {
                "id": spec["id"],
                "name": spec["name"],
                "available": False,
                "enabled": False,
            }

        info = NodeRequests(
            address=spec["address"],
            port=spec["port"],
            api_key=spec["key"],
            tunnel_address=spec["tunnel_address"],
            protocol=spec["protocol"],
            ovpn_port=spec["ovpn_port"],
            set_new_setting=False,
        ).get_node_info()

        if not info:
            return {
                "id": spec["id"],
                "name": spec["name"],
                "available": False,
                "enabled": True,
            }

        return {
            "id": spec["id"],
            "name": spec["name"],
            "available": True,
            "enabled": True,

            # Timestamp belongs to THIS node response,
            # not to the slowest node in asyncio.gather.
            "_sample_mono": time.monotonic(),

            **info,
        }

    results = await asyncio.gather(
        *[
            asyncio.to_thread(
                read_node,
                spec,
            )
            for spec in node_specs
        ]
    )

    # OV_DASHBOARD_SERVER_RATE_PROCESS_V2
    #
    # The UI refreshes every second, but rate is derived from
    # approximately a 3-second rolling counter window.
    #
    # This is still realtime (new value every ~1 second),
    # while eliminating latency/jitter spikes.

    active_node_ids = set()

    for row in results:

        if (
            not isinstance(row, dict)
            or not row.get("available")
        ):
            continue

        try:
            node_id = int(row["id"])

            rx = int(
                row.get(
                    "rx_bytes",
                    0,
                )
                or 0
            )

            tx = int(
                row.get(
                    "tx_bytes",
                    0,
                )
                or 0
            )

            sample_mono = float(
                row.pop(
                    "_sample_mono",
                    time.monotonic(),
                )
            )

        except Exception:

            row["rate_ready"] = False
            row["download_bps"] = 0.0
            row["upload_bps"] = 0.0
            continue


        active_node_ids.add(
            node_id
        )


        state = (
            _dashboard_rate_state
            .setdefault(
                node_id,
                {
                    "samples": [],
                    "download_bps": 0.0,
                    "upload_bps": 0.0,
                    "ready": False,
                    "window_seconds": 0.0,
                },
            )
        )

        samples = state[
            "samples"
        ]


        # --------------------------------------------------
        # Ignore an older/out-of-order concurrent response.
        # --------------------------------------------------

        if (
            samples
            and sample_mono
            <= samples[-1][0]
        ):

            row["download_bps"] = (
                state["download_bps"]
            )

            row["upload_bps"] = (
                state["upload_bps"]
            )

            row["rate_ready"] = (
                state["ready"]
            )

            row["rate_window_seconds"] = (
                state["window_seconds"]
            )

            continue


        # --------------------------------------------------
        # Counter reset / reboot / interface reset
        # --------------------------------------------------

        if samples:

            last = samples[-1]

            if (
                rx < last[1]
                or tx < last[2]
            ):
                samples = []


        samples.append(
            (
                sample_mono,
                rx,
                tx,
            )
        )


        # Keep enough history for a stable 3-second window.
        samples = [
            sample
            for sample in samples
            if (
                sample_mono
                - sample[0]
            ) <= 5.5
        ][-8:]


        state["samples"] = (
            samples
        )


        previous_samples = (
            samples[:-1]
        )


        if previous_samples:

            # Pick the historical sample closest to
            # three seconds ago.
            candidates = [
                sample
                for sample
                in previous_samples
                if (
                    sample_mono
                    - sample[0]
                ) >= 0.75
            ]


            if candidates:

                base = min(
                    candidates,
                    key=lambda sample: abs(
                        (
                            sample_mono
                            - sample[0]
                        )
                        - 3.0
                    ),
                )

                elapsed = (
                    sample_mono
                    - base[0]
                )


                if elapsed >= 0.75:

                    rx_rate = (
                        max(
                            0,
                            rx - base[1],
                        )
                        / elapsed
                    )

                    tx_rate = (
                        max(
                            0,
                            tx - base[2],
                        )
                        / elapsed
                    )


                    # User/network perspective:
                    #
                    # Server TX -> data sent to VPN clients
                    #            -> Download
                    #
                    # Server RX -> data received from clients
                    #            -> Upload

                    state[
                        "download_bps"
                    ] = tx_rate

                    state[
                        "upload_bps"
                    ] = rx_rate

                    state[
                        "window_seconds"
                    ] = elapsed

                    state[
                        "ready"
                    ] = True


        row["download_bps"] = (
            float(
                state[
                    "download_bps"
                ]
            )
        )

        row["upload_bps"] = (
            float(
                state[
                    "upload_bps"
                ]
            )
        )

        row["rate_ready"] = (
            bool(
                state[
                    "ready"
                ]
            )
        )

        row[
            "rate_window_seconds"
        ] = round(
            float(
                state[
                    "window_seconds"
                ]
            ),
            3,
        )


    # Remove histories for deleted nodes.
    for node_id in list(
        _dashboard_rate_state
    ):

        if (
            node_id
            not in active_node_ids
        ):

            _dashboard_rate_state.pop(
                node_id,
                None,
            )


    payload = {
        "nodes": results,

        # Exact sample time used by the browser
        # to calculate counter deltas correctly.
        "sample_time": time.time(),

        # Kept for compatibility.
        "timestamp": int(time.time()),
    }

    _dashboard_live_cache["time"] = (
        time.monotonic()
    )

    _dashboard_live_cache["data"] = payload

    return {
        "success": True,
        "msg": "Dashboard live metrics retrieved",
        "data": payload,
    }


# PATCH1_MONITORING_WEB
import time, urllib.parse, urllib.request
from pydantic import BaseModel, Field
from fastapi import HTTPException
from backend.db.models import MonitoringSettings
from backend.monitoring_crypto import encrypt_secret, decrypt_secret
class MonitoringUpdate(BaseModel):
    enabled: bool=False; telegram_token: str|None=Field(None,max_length=512); telegram_chat_id: str|None=Field(None,max_length=128)
    node_status_alerts: bool=True
    cpu_limit: int=Field(85,ge=1,le=100); ram_limit: int=Field(85,ge=1,le=100); disk_limit: int=Field(85,ge=1,le=100)
    ssl_host: str|None=Field(None,max_length=255); ssl_port: int=Field(443,ge=1,le=65535); ssl_warning_days: int=Field(14,ge=1,le=365)
def _mr(db):
    r=db.query(MonitoringSettings).filter(MonitoringSettings.id==1).first()
    if not r: r=MonitoringSettings(id=1); db.add(r); db.commit(); db.refresh(r)
    return r
def _mo(r): return {'enabled':r.enabled,'telegram_configured':bool(r.telegram_token_encrypted and r.telegram_chat_id),'telegram_chat_id':r.telegram_chat_id or '',
 'cpu_limit':r.cpu_limit,'ram_limit':r.ram_limit,'disk_limit':r.disk_limit,'node_status_alerts':getattr(r,'node_status_alerts',True),'ssl_host':r.ssl_host or '','ssl_port':r.ssl_port,'ssl_warning_days':r.ssl_warning_days}
def _tg(token,chat,text):
    data=urllib.parse.urlencode({'chat_id':chat,'text':text}).encode()
    with urllib.request.urlopen(urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMessage',data=data,method='POST'),timeout=15) as x:
        if x.status!=200: raise RuntimeError('Telegram HTTP error')
@router.get('/monitoring',response_model=ResponseModel)
async def monitoring_get(db:Session=Depends(get_db),user:dict=Depends(get_current_user)):
    if user['type']!='main_admin': raise HTTPException(403,'Main administrator required')
    return ResponseModel(success=True,msg='Monitoring settings',data=_mo(_mr(db)))
@router.put('/monitoring',response_model=ResponseModel)
async def monitoring_put(q:MonitoringUpdate,db:Session=Depends(get_db),user:dict=Depends(get_current_user)):
    if user['type']!='main_admin': raise HTTPException(403,'Main administrator required')
    r=_mr(db)
    if q.telegram_token and q.telegram_token.strip(): r.telegram_token_encrypted=encrypt_secret(q.telegram_token.strip())
    r.enabled=q.enabled; r.telegram_chat_id=(q.telegram_chat_id or '').strip() or None; r.cpu_limit=q.cpu_limit; r.ram_limit=q.ram_limit; r.disk_limit=q.disk_limit; r.node_status_alerts=q.node_status_alerts
    r.ssl_host=(q.ssl_host or '').strip() or None; r.ssl_port=q.ssl_port; r.ssl_warning_days=q.ssl_warning_days; r.updated_at=int(time.time()); r.updated_by=user['username']
    if r.enabled and not(r.telegram_token_encrypted and r.telegram_chat_id): raise HTTPException(422,'Telegram token and Chat ID are required')
    db.commit(); db.refresh(r); return ResponseModel(success=True,msg='Monitoring settings saved',data=_mo(r))
@router.post('/monitoring/test',response_model=ResponseModel)
async def monitoring_test(db:Session=Depends(get_db),user:dict=Depends(get_current_user)):
    if user['type']!='main_admin': raise HTTPException(403,'Main administrator required')
    r=_mr(db); token=decrypt_secret(r.telegram_token_encrypted)
    if not token or not r.telegram_chat_id: raise HTTPException(422,'Telegram is not configured')
    try: _tg(token,r.telegram_chat_id,'✅ PVNetwork Panel Telegram monitoring test succeeded.')
    except Exception as e: raise HTTPException(502,f'Telegram test failed: {type(e).__name__}')
    return ResponseModel(success=True,msg='Telegram test message sent',data=None)
