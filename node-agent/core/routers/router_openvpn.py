from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import json
import os
import subprocess

from core.auth.auth import check_api_key
from core.schema.all_schemas import ResponseModel

router = APIRouter(prefix="/router-openvpn", tags=["router_openvpn"])
HELPER = "/usr/local/sbin/pvnetwork-router-openvpn"
ROUTER_STATUS_FILE = "/var/log/openvpn-router-status.log"


class RouterOpenVpnConfigRequest(BaseModel):
    enabled: bool = True
    port: int = Field(default=1195, ge=1, le=65535)
    protocol: str = "tcp"
    subnet: str = "10.9.0.0/24"


class RouterOpenVpnCredentialRequest(BaseModel):
    cn: str
    username: str
    verifier: str
    enabled: bool = True


def _call(*args: str, timeout: int = 30) -> dict:
    if not os.path.isfile(HELPER):
        return {
            "ok": False,
            "capable": False,
            "upgrade_required": True,
            "error": "router capability missing",
        }
    try:
        result = subprocess.run(
            [HELPER, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)[:300]}
    text = (result.stdout or "").strip()
    if result.returncode != 0:
        return {
            "ok": False,
            "error": (result.stderr or text or "router helper failed")[-500:],
        }
    try:
        data = json.loads(text) if text.startswith("{") else {"ok": True, "path": text}
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid router helper response"}
    data.setdefault("ok", True)
    return data


def _online_common_names() -> list[str]:
    names: set[str] = set()
    if not os.path.isfile(ROUTER_STATUS_FILE):
        return []
    try:
        with open(ROUTER_STATUS_FILE, "r", encoding="utf-8", errors="ignore") as stream:
            for raw in stream:
                if not raw.startswith("CLIENT_LIST,"):
                    continue
                parts = raw.rstrip("\r\n").split(",")
                if len(parts) < 2 or parts[1] in {"", "Common Name", "UNDEF"}:
                    continue
                names.add(parts[1])
    except OSError:
        return []
    return sorted(names)


@router.get("/status")
async def status(api_key: str = Depends(check_api_key)):
    data = _call("status")
    common_names = _online_common_names()
    data["online_common_names"] = common_names
    data["online_clients"] = len(common_names)
    return ResponseModel(success=bool(data.get("ok")), msg="Router OpenVPN status", data=data)


@router.post("/preflight")
async def preflight(request: RouterOpenVpnConfigRequest, api_key: str = Depends(check_api_key)):
    data = _call(
        "preflight", "--port", str(request.port), "--protocol", request.protocol,
        "--subnet", request.subnet,
    )
    return ResponseModel(success=bool(data.get("ok")), msg="Router OpenVPN preflight", data=data)


@router.put("/config")
async def config(request: RouterOpenVpnConfigRequest, api_key: str = Depends(check_api_key)):
    args = ["enable" if request.enabled else "disable"]
    if request.enabled:
        args += [
            "--port", str(request.port), "--protocol", request.protocol,
            "--subnet", request.subnet,
        ]
    data = _call(*args, timeout=60)
    return ResponseModel(success=bool(data.get("ok")), msg="Router OpenVPN configuration", data=data)


@router.put("/credential")
async def credential(request: RouterOpenVpnCredentialRequest, api_key: str = Depends(check_api_key)):
    if request.enabled:
        data = _call(
            "credential-set", "--cn", request.cn, "--username", request.username,
            "--verifier", request.verifier, "--enabled", "1",
        )
    else:
        data = _call("credential-revoke", "--cn", request.cn)
    return ResponseModel(success=bool(data.get("ok")), msg="Router OpenVPN credential", data=data)


@router.get("/profile/{cn}")
async def profile(cn: str, api_key: str = Depends(check_api_key)):
    data = _call("profile", "--cn", cn)
    path = str(data.get("path") or "")
    if data.get("ok") and path and os.path.isfile(path):
        return FileResponse(
            path=path,
            filename=f"{cn}.router.ovpn",
            media_type="application/x-openvpn-profile",
        )
    return ResponseModel(success=False, msg="Router OpenVPN profile unavailable", data=data)
