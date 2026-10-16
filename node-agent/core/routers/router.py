from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import psutil
import time
import json
import asyncio
import urllib.request
import urllib.error
from core.controller_transport import open_controller,require_local_hook
from core.schema.all_schemas import User, ResponseModel, SetSettingsModel, NativeConfigurationRequest
from core.auth.auth import check_api_key
from core.config import settings
from core.service.user_managment import (
    create_user_on_server,
    change_user_status as change_user_status_on_server,
    delete_user_on_server,
    download_ovpn_file,
    get_users_usage,
    get_user_identity_state,
)
from core.setting.core import change_config, native_operation, native_manager


router = APIRouter(prefix="/sync", tags=["node_sync"])


# ============================================================
# PVNETWORK_DASHBOARD_NODE_METRICS_V1
# Lightweight node-level metrics for the PVNetwork Panel dashboard.
# No per-user polling is performed here.
# ============================================================

def _pvnetwork_dashboard_default_interface():
    """
    Detect the interface that owns the Linux default route.
    This prevents lo/tun interfaces from being double-counted.
    """

    try:
        with open(
            "/proc/net/route",
            "r",
            encoding="utf-8",
        ) as route_file:
            next(route_file, None)

            for raw in route_file:
                parts = raw.split()

                if len(parts) < 4:
                    continue

                interface = parts[0]
                destination = parts[1]

                try:
                    flags = int(parts[3], 16)
                except ValueError:
                    continue

                if (
                    destination == "00000000"
                    and flags & 0x2
                ):
                    return interface

    except Exception:
        pass

    # Safe fallback: busiest non-loopback interface.
    counters = psutil.net_io_counters(pernic=True)

    candidates = []

    for name, io in counters.items():
        if name == "lo":
            continue

        candidates.append(
            (
                int(io.bytes_recv or 0)
                + int(io.bytes_sent or 0),
                name,
            )
        )

    if not candidates:
        return None

    candidates.sort(reverse=True)

    return candidates[0][1]



# ============================================================
# PVNETWORK_REAL_OPENVPN_ONLINE_V1
# online_count    = unique Common Names
# online_sessions = active OpenVPN sessions
# ============================================================

def _pvnetwork_openvpn_status_file():
    config_path = "/etc/openvpn/server/server.conf"

    try:
        with open(
            config_path,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as config:
            for raw in config:
                line = raw.strip()

                if (
                    not line
                    or line.startswith("#")
                    or line.startswith(";")
                ):
                    continue

                parts = line.split()

                if (
                    len(parts) >= 2
                    and parts[0] == "status"
                ):
                    return parts[1]

    except Exception:
        pass

    return settings.openvpn_status_file


def _pvnetwork_openvpn_online_snapshot():
    path = _pvnetwork_openvpn_status_file()

    common_names = set()
    sessions = 0

    try:
        with open(
            path,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as status_file:

            for raw in status_file:
                if not raw.startswith("CLIENT_LIST,"):
                    continue

                parts = raw.rstrip(
                    "\r\n"
                ).split(",")

                if len(parts) < 2:
                    continue

                common_name = parts[1].strip()

                sessions += 1

                if (
                    common_name
                    and common_name != "UNDEF"
                ):
                    common_names.add(
                        common_name
                    )

    except Exception:
        return {
            "online_count": 0,
            "online_sessions": 0,
            "openvpn_status_file": path,
        }

    return {
        "online_count": len(common_names),
        "online_sessions": sessions,
        "openvpn_status_file": path,
    }


def _pvnetwork_dashboard_network_snapshot():
    interface = _pvnetwork_dashboard_default_interface()

    result = {
        "network_interface": interface,
        "uptime": int(
            max(
                0,
                time.time() - psutil.boot_time(),
            )
        ),
        "boot_time": int(psutil.boot_time()),
        "rx_bytes": 0,
        "tx_bytes": 0,
        "traffic_bytes": 0,
    }

    if not interface:
        return result

    counters = psutil.net_io_counters(pernic=True)

    io = counters.get(interface)

    if io is None:
        return result

    rx = int(io.bytes_recv or 0)
    tx = int(io.bytes_sent or 0)

    result.update(
        {
            "rx_bytes": rx,
            "tx_bytes": tx,
            "traffic_bytes": rx + tx,
        }
    )

    return result


@router.get("/status", response_model=ResponseModel)
async def get_status(request: SetSettingsModel, api_key: str = Depends(check_api_key)):
    """Get the current status of the node and set ovpn settings"""
    if request.set_new_setting:
        change_settings = await asyncio.to_thread(change_config,request)
        if not change_settings:
            return ResponseModel(success=False, msg="Failed to change settings")

    from pathlib import Path
    status = {"status": "running", "version":(Path(__file__).resolve().parents[2]/'VERSION').read_text().strip(),"agent":"pvnetwork-node","tls":True}
    if native_manager() is not None:status['configuration_transaction']='v1'
    cpu_usage = psutil.cpu_percent()
    memory_info = psutil.virtual_memory()
    status.update(
        {
            "cpu_usage": cpu_usage,
            "memory_usage": memory_info.percent,
        }
    )

    status.update(
        _pvnetwork_dashboard_network_snapshot()
    )

    status.update(
        _pvnetwork_openvpn_online_snapshot()
    )
    return ResponseModel(
        success=True, msg="Node status retrieved successfully", data=status
    )


@router.post('/configuration',response_model=ResponseModel)
async def prepare_configuration(request:NativeConfigurationRequest,api_key:str=Depends(check_api_key)):
    scoped=SetSettingsModel(**request.model_dump(exclude={'transaction_id'}))
    try:result=await asyncio.to_thread(native_operation,'configure',scoped,transaction_id=request.transaction_id)
    except ValueError:raise HTTPException(status_code=409,detail='Native configuration could not reach ready state; inspect its private transaction') from None
    return ResponseModel(success=True,msg='Native configuration prepared',data=result)


@router.post('/configuration/{transaction_id}/finalize',response_model=ResponseModel)
async def finalize_configuration(transaction_id:str,api_key:str=Depends(check_api_key)):
    try:result=await asyncio.to_thread(native_operation,'finalize-configuration',transaction_id=transaction_id)
    except ValueError:raise HTTPException(status_code=409,detail='Native configuration finalization requires recovery') from None
    return ResponseModel(success=True,msg='Native configuration finalized',data=result)


@router.post('/configuration/{transaction_id}/rollback',response_model=ResponseModel)
async def rollback_configuration(transaction_id:str,api_key:str=Depends(check_api_key)):
    try:result=await asyncio.to_thread(native_operation,'rollback-configuration',transaction_id=transaction_id)
    except ValueError:raise HTTPException(status_code=409,detail='Native configuration rollback requires inspection') from None
    return ResponseModel(success=True,msg='Native configuration rollback resolved',data=result)


@router.get("/usage", response_model=ResponseModel)
async def get_all_user_usage(api_key: str = Depends(check_api_key)):
    usages = get_users_usage()
    if usages:
        return ResponseModel(success=True, msg="Latest user usage received", data=usages) 
    return ResponseModel(success=True, msg="No user is using it.",)



@router.post("/user", response_model=ResponseModel)
async def create_user(user: User, api_key: str = Depends(check_api_key)):
    success = await asyncio.to_thread(create_user_on_server,user.name)
    if success:
        return ResponseModel(
            success=True,
            msg="User created successfully",
            data={"client_name": user.name},
        )
    return ResponseModel(success=False, msg="Failed to create user")


@router.get("/user/{name}/identity", response_model=ResponseModel)
async def get_user_identity(name: str, api_key: str = Depends(check_api_key)):
    data = get_user_identity_state(name)
    return ResponseModel(success=True, msg="User identity state", data=data)


@router.delete("/user/{name}", response_model=ResponseModel)
async def delete_user(name: str, api_key: str = Depends(check_api_key)):
    result = await asyncio.to_thread(delete_user_on_server,name)
    if result:
        return ResponseModel(
            success=True,
            msg="User deleted successfully",
            data={"client_name": name},
        )
    return ResponseModel(success=False, msg="Failed to delete user")


@router.put("/user", response_model=ResponseModel)
async def change_user_status(user: User, api_key: str = Depends(check_api_key)):
    result = await asyncio.to_thread(change_user_status_on_server,user.name,user.status)
    if result:
        return ResponseModel(
            success=True,
            msg="User status changed successfully",
            data={"client_name": user.name},
        )
    return ResponseModel(success=False, msg="Failed to change user status")


@router.get("/download/ovpn/{client_name}")
async def download_ovpn(client_name: str, api_key: str = Depends(check_api_key)):
    response = await download_ovpn_file(client_name)
    if response:
        return FileResponse(
            path=response,
            filename=f"{client_name}.ovpn",
            media_type="application/x-openvpn-profile",
        )
    else:
        return ResponseModel(success=False, msg="OVPN file not found", data=None)



# ============================================================
# PVNETWORK_LOCAL_SESSION_PROXY_V2
#
# Local-only bridge:
# OpenVPN(nobody) -> 127.0.0.1 PVNetwork Node(root) -> PVNetwork Panel
#
# The OpenVPN process never reads or receives the node API key.
# ============================================================

_SESSION_PANEL_BASE = settings.panel_url.rstrip('/') + '/api/integrations/mirza/session'

_SESSION_ACTIONS = {
    "acquire",
    "heartbeat",
    "release",
    "snapshot",
}


def _session_proxy_to_panel(action: str, payload: dict):
    if not settings.panel_url:
        return JSONResponse(status_code=503,content={'success':False,'detail':'Controller callback is not configured'})
    url = f"{_SESSION_PANEL_BASE}/{action}"

    if action == "snapshot":
        body_payload = {
            "sessions": payload["sessions"],
        }
    else:
        body_payload = {
            "common_name": payload["common_name"],
            "remote_addr": payload["remote_addr"],
        }

    body = json.dumps(
        body_payload
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-PVNetwork-Node-Key": settings.api_key,
        },
    )

    try:
        with open_controller(
            request,
            timeout=6,
        ) as response:
            status_code = response.status
            raw = response.read().decode(
                "utf-8",
                errors="replace",
            )

    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw = exc.read().decode(
            "utf-8",
            errors="replace",
        )

    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "detail": (
                    "Central session controller "
                    "is unavailable"
                ),
                "error": type(exc).__name__,
            },
        )

    try:
        content = json.loads(raw) if raw else {}
    except Exception:
        content = {
            "raw": raw[:500],
        }

    return JSONResponse(
        status_code=status_code,
        content=content,
    )


@router.post("/local-session/{action}")
async def local_session_proxy(
    action: str,
    payload: dict,
    request: Request,
):
    require_local_hook(request)
    # The TLS API can listen publicly; hook requests are local and separately
    # authenticated without exposing the controller/node API key to OpenVPN.
    client_host = (
        request.client.host
        if request.client
        else ""
    )

    if client_host not in {
        "127.0.0.1",
        "::1",
    }:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "detail": "Local access only",
            },
        )

    if action not in _SESSION_ACTIONS:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "detail": "Unknown session action",
            },
        )

    if action == "snapshot":
        raw_sessions = payload.get("sessions")

        if (
            not isinstance(raw_sessions, list)
            or len(raw_sessions) > 4096
        ):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "detail": "Invalid session snapshot",
                },
            )

        sessions = []
        seen = set()

        for item in raw_sessions:
            if not isinstance(item, dict):
                return JSONResponse(
                    status_code=422,
                    content={
                        "success": False,
                        "detail": "Invalid snapshot entry",
                    },
                )

            common_name = str(
                item.get("common_name", "")
            ).strip()

            remote_addr = str(
                item.get("remote_addr", "")
            ).strip()

            if (
                not common_name
                or not remote_addr
                or len(common_name) > 128
                or len(remote_addr) > 256
            ):
                return JSONResponse(
                    status_code=422,
                    content={
                        "success": False,
                        "detail": "Invalid snapshot entry",
                    },
                )

            identity = (
                common_name,
                remote_addr,
            )

            if identity in seen:
                continue

            seen.add(identity)
            sessions.append(
                {
                    "common_name": common_name,
                    "remote_addr": remote_addr,
                }
            )

        return _session_proxy_to_panel(
            action,
            {
                "sessions": sessions,
            },
        )

    common_name = str(
        payload.get("common_name", "")
    ).strip()

    remote_addr = str(
        payload.get("remote_addr", "")
    ).strip()

    if (
        not common_name
        or not remote_addr
        or len(common_name) > 128
        or len(remote_addr) > 256
    ):
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "detail": "Invalid session payload",
            },
        )

    return _session_proxy_to_panel(
        action,
        {
            "common_name": common_name,
            "remote_addr": remote_addr,
        },
    )


# PVNETWORK_DOMAIN_HISTORY_INCLUDE_V1
from core.routers.domain_history import router as domain_history_router

router.include_router(domain_history_router)

# PVNETWORK_ROUTER_OPENVPN_INCLUDE_V1
from core.routers.router_openvpn import router as router_openvpn_router
router.include_router(router_openvpn_router)
