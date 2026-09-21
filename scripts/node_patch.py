#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

USER_MANAGEMENT = r'''import os
import re
import subprocess

from core.logger import logger
from core.schema.all_schemas import UsersUsage

PROFILE_BUILDER = "/usr/local/sbin/pvnetwork-build-client-profile"
INSTALLER = "/root/openvpn-install.sh"
CCD_DIR = "/etc/openvpn/server/ccd"
MGMT_SOCKET = "/var/run/openvpn-server/server.sock"


def _safe_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(name or "")))


def _profile_valid(name: str) -> bool:
    path = f"/root/{name}.ovpn"
    if not os.path.isfile(path) or os.path.getsize(path) < 500:
        return False
    try:
        text = open(path, "r", encoding="utf-8", errors="ignore").read().lower()
    except OSError:
        return False
    return all(x in text for x in ("<ca>", "</ca>", "<cert>", "</cert>", "<key>", "</key>"))


def _touch_ccd(name: str) -> None:
    os.makedirs(CCD_DIR, exist_ok=True)
    path = os.path.join(CCD_DIR, name)
    open(path, "a").close()
    os.chmod(path, 0o644)


def _disconnect(name: str) -> None:
    if not os.path.exists(MGMT_SOCKET):
        return
    try:
        subprocess.run(
            ["socat", "-", f"UNIX-CONNECT:{MGMT_SOCKET}"],
            input=f"kill {name}\nquit\n",
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except Exception:
        pass


def create_user_on_server(name) -> bool:
    name = str(name or "").strip()
    if not _safe_name(name):
        logger.error("Invalid OpenVPN client name: %s", name)
        return False
    if _profile_valid(name):
        _touch_ccd(name)
        return True
    if not os.path.isfile(PROFILE_BUILDER):
        logger.error("Profile builder missing: %s", PROFILE_BUILDER)
        return False
    try:
        result = subprocess.run(
            [PROFILE_BUILDER, name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=240,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("Profile builder timed out for %s", name)
        return False
    ok = result.returncode == 0 and _profile_valid(name)
    if not ok:
        logger.error("Profile builder failed for %s: %s", name, (result.stdout or "")[-2000:])
        return False
    _touch_ccd(name)
    return True


def delete_user_on_server(name) -> bool | str:
    name = str(name or "").strip()
    if not _safe_name(name):
        return False
    _disconnect(name)
    result = None
    if os.path.isfile(INSTALLER):
        try:
            result = subprocess.run(
                ["bash", INSTALLER, "client", "revoke", name, "--force"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=180,
                check=False,
            )
        except Exception as exc:
            logger.error("Revoke failed for %s: %s", name, exc)
    for path in (
        f"/root/{name}.ovpn",
        f"/etc/openvpn/server/ccd/{name}",
        f"/etc/openvpn/ccd/{name}",
    ):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    if result is None:
        return False
    if result.returncode == 0:
        return True
    output = (result.stdout or "").lower()
    if any(x in output for x in ("not found", "does not exist", "already revoked")):
        return "not_found"
    return False


def change_user_status(name: str, status: str) -> bool:
    name = str(name or "").strip()
    if not _safe_name(name):
        return False
    path = os.path.join(CCD_DIR, name)
    try:
        if status == "deactivate":
            if os.path.exists(path):
                os.remove(path)
            _disconnect(name)
            return True
        if status == "activate":
            if not _profile_valid(name) and not create_user_on_server(name):
                return False
            _touch_ccd(name)
            return True
        return False
    except Exception as exc:
        logger.error("Status change failed for %s: %s", name, exc)
        return False


def restart_openvpn_service() -> bool:
    # Kept for compatibility. PVNetwork intentionally avoids routine OpenVPN restarts.
    return True


async def download_ovpn_file(name: str) -> str | None:
    name = str(name or "").strip()
    if not _safe_name(name):
        return None
    path = f"/root/{name}.ovpn"
    if _profile_valid(name):
        return path
    if create_user_on_server(name) and _profile_valid(name):
        return path
    return None


def get_users_usage() -> UsersUsage | None:
    users = {}
    candidates = ("/var/log/openvpn/status.log", "/var/log/openvpn-status.log")
    file_path = next((p for p in candidates if os.path.isfile(p)), None)
    if not file_path:
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as stream:
            for raw in stream:
                line = raw.strip()
                if not line.startswith("CLIENT_LIST") or line.startswith("CLIENT_LIST,Common Name"):
                    continue
                parts = line.split(",")
                if len(parts) < 7:
                    continue
                try:
                    users[parts[1]] = int(parts[5]) + int(parts[6])
                except (ValueError, IndexError):
                    continue
    except OSError:
        return None
    return UsersUsage(users=users) if users else None
'''

ROUTER = r'''from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import json
import os
import psutil
import subprocess

from core.schema.all_schemas import User, ResponseModel, SetSettingsModel
from core.auth.auth import check_api_key
from core.service.user_managment import (
    create_user_on_server,
    change_user_status as change_user_status_on_server,
    delete_user_on_server,
    download_ovpn_file,
    get_users_usage,
)
from core.setting.core import change_config

router = APIRouter(prefix="/sync", tags=["node_sync"])

ROUTER_OPENVPN_HELPER = "/usr/local/sbin/pvnetwork-router-openvpn"


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


def _router_openvpn_call(*args: str, timeout: int = 30) -> dict:
    if not os.path.isfile(ROUTER_OPENVPN_HELPER):
        return {"ok": False, "capable": False, "upgrade_required": True, "error": "router capability missing"}
    try:
        result = subprocess.run(
            [ROUTER_OPENVPN_HELPER, *args],
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
        return {"ok": False, "error": (result.stderr or text or "router helper failed")[-500:]}
    try:
        data = json.loads(text) if text.startswith("{") else {"ok": True, "path": text}
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid router helper response"}
    data.setdefault("ok", True)
    return data


def _default_interface() -> str:
    try:
        with open("/proc/net/route", "r", encoding="utf-8") as stream:
            next(stream, None)
            for line in stream:
                parts = line.split()
                if len(parts) >= 4 and parts[1] == "00000000" and int(parts[3], 16) & 2:
                    return parts[0]
    except Exception:
        pass
    stats = psutil.net_if_stats()
    for name, state in stats.items():
        if name != "lo" and state.isup:
            return name
    return ""


def _counter(interface: str, name: str) -> int:
    if not interface:
        return 0
    try:
        return int(open(f"/sys/class/net/{interface}/statistics/{name}", "r").read().strip())
    except Exception:
        return 0


def _online_users() -> int:
    for path in ("/var/log/openvpn/status.log", "/var/log/openvpn-status.log"):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as stream:
                return sum(1 for line in stream if line.startswith("CLIENT_LIST,") and not line.startswith("CLIENT_LIST,Common Name"))
        except OSError:
            pass
    return 0


def _router_online_common_names() -> list[str]:
    path = "/var/log/openvpn-router-status.log"
    names: set[str] = set()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as stream:
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


def _router_openvpn_snapshot() -> dict:
    data = _router_openvpn_call("status")
    if not isinstance(data, dict):
        data = {"ok": False, "capable": False}
    result = dict(data)
    result["online_common_names"] = _router_online_common_names()
    result["online_clients"] = len(result["online_common_names"])
    return result


@router.get("/status", response_model=ResponseModel)
async def get_status(request: SetSettingsModel, api_key: str = Depends(check_api_key)):
    if request.set_new_setting:
        if not change_config(request):
            return ResponseModel(success=False, msg="Failed to change settings")

    interface = _default_interface()
    rx_bytes = _counter(interface, "rx_bytes")
    tx_bytes = _counter(interface, "tx_bytes")
    status = {
        "status": "running",
        "cpu_usage": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
        "uptime": max(0, int(psutil.boot_time() and (__import__('time').time() - psutil.boot_time()))),
        "boot_time": int(psutil.boot_time()),
        "network_interface": interface,
        "rx_bytes": rx_bytes,
        "tx_bytes": tx_bytes,
        "traffic_bytes": rx_bytes + tx_bytes,
        "online_users": _online_users(),
    }
    status["router_openvpn"] = _router_openvpn_snapshot()
    return ResponseModel(success=True, msg="Node status retrieved successfully", data=status)


@router.get("/usage", response_model=ResponseModel)
async def get_all_user_usage(api_key: str = Depends(check_api_key)):
    usages = get_users_usage()
    if usages:
        return ResponseModel(success=True, msg="Latest user usage received", data=usages)
    return ResponseModel(success=True, msg="No user is using it.", data=None)


@router.post("/user", response_model=ResponseModel)
async def create_user(user: User, api_key: str = Depends(check_api_key)):
    success = create_user_on_server(user.name)
    if success:
        return ResponseModel(success=True, msg="User created successfully", data={"client_name": user.name})
    return ResponseModel(success=False, msg="Failed to create user")


@router.delete("/user/{name}", response_model=ResponseModel)
async def delete_user(name: str, api_key: str = Depends(check_api_key)):
    result = delete_user_on_server(name)
    if result:
        return ResponseModel(success=True, msg="User deleted successfully", data={"client_name": name})
    return ResponseModel(success=False, msg="Failed to delete user")


@router.put("/user", response_model=ResponseModel)
async def change_user_status(user: User, api_key: str = Depends(check_api_key)):
    result = change_user_status_on_server(user.name, user.status)
    if result:
        return ResponseModel(success=True, msg="User status changed successfully", data={"client_name": user.name})
    return ResponseModel(success=False, msg="Failed to change user status")


@router.get("/download/ovpn/{client_name}")
async def download_ovpn(client_name: str, api_key: str = Depends(check_api_key)):
    path = await download_ovpn_file(client_name)
    if path:
        return FileResponse(path=path, filename=f"{client_name}.ovpn", media_type="application/x-openvpn-profile")
    return ResponseModel(success=False, msg="OVPN file not found", data=None)


@router.get("/router-openvpn/status")
async def router_openvpn_status(api_key: str = Depends(check_api_key)):
    data = _router_openvpn_snapshot()
    return ResponseModel(success=bool(data.get("ok")), msg="Router OpenVPN status", data=data)


@router.post("/router-openvpn/preflight")
async def router_openvpn_preflight(request: RouterOpenVpnConfigRequest, api_key: str = Depends(check_api_key)):
    data = _router_openvpn_call(
        "preflight", "--port", str(request.port), "--protocol", request.protocol, "--subnet", request.subnet
    )
    return ResponseModel(success=bool(data.get("ok")), msg="Router OpenVPN preflight", data=data)


@router.put("/router-openvpn/config")
async def router_openvpn_config(request: RouterOpenVpnConfigRequest, api_key: str = Depends(check_api_key)):
    args = ["enable" if request.enabled else "disable"]
    if request.enabled:
        args += ["--port", str(request.port), "--protocol", request.protocol, "--subnet", request.subnet]
    data = _router_openvpn_call(*args, timeout=60)
    return ResponseModel(success=bool(data.get("ok")), msg="Router OpenVPN configuration", data=data)


@router.put("/router-openvpn/credential")
async def router_openvpn_credential(request: RouterOpenVpnCredentialRequest, api_key: str = Depends(check_api_key)):
    if request.enabled:
        data = _router_openvpn_call(
            "credential-set", "--cn", request.cn, "--username", request.username,
            "--verifier", request.verifier, "--enabled", "1",
        )
    else:
        data = _router_openvpn_call("credential-revoke", "--cn", request.cn)
    return ResponseModel(success=bool(data.get("ok")), msg="Router OpenVPN credential", data=data)


@router.get("/router-openvpn/profile/{cn}")
async def router_openvpn_profile(cn: str, api_key: str = Depends(check_api_key)):
    data = _router_openvpn_call("profile", "--cn", cn)
    path = str(data.get("path") or "")
    if data.get("ok") and path and os.path.isfile(path):
        return FileResponse(path=path, filename=f"{cn}.router.ovpn", media_type="application/x-openvpn-profile")
    return ResponseModel(success=False, msg="Router OpenVPN profile unavailable", data=data)
'''


ROUTER_OPENVPN_MODULE = r'''from fastapi import APIRouter, Depends
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
'''


USER_LIFECYCLE_NO_RESTART = r'''# PVNETWORK_USER_LIFECYCLE_NO_RESTART_V1
_PVNETWORK_SERVER_CONF = os.getenv("PVNETWORK_OPENVPN_SERVER_CONF", "/etc/openvpn/server/server.conf")
_PVNETWORK_EASYRSA_DIR = os.getenv("PVNETWORK_EASYRSA_DIR", "/etc/openvpn/server/easy-rsa")
_PVNETWORK_MGMT_SOCKETS = (
    os.getenv("PVNETWORK_OPENVPN_MANAGEMENT_SOCKET", "/run/openvpn/ov-management.sock"),
    "/var/run/openvpn-server/server.sock",
)


def _pvnetwork_ccd_dirs() -> list[str]:
    candidates: list[str] = []
    try:
        with open(_PVNETWORK_SERVER_CONF, "r", encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                parts = raw.strip().split()
                if len(parts) >= 2 and parts[0] == "client-config-dir":
                    value = parts[1]
                    if not os.path.isabs(value):
                        value = os.path.join(os.path.dirname(_PVNETWORK_SERVER_CONF), value)
                    candidates.append(value)
                    break
    except OSError:
        pass
    candidates.extend(("/etc/openvpn/ccd", "/etc/openvpn/server/ccd"))
    result: list[str] = []
    for value in candidates:
        if value and value not in result:
            result.append(value)
    return result


def _pvnetwork_touch_ccd(name: str) -> None:
    ccd_dir = _pvnetwork_ccd_dirs()[0]
    os.makedirs(ccd_dir, exist_ok=True)
    path = os.path.join(ccd_dir, name)
    open(path, "a").close()
    os.chmod(path, 0o644)


def _pvnetwork_remove_ccd(name: str) -> None:
    for ccd_dir in _pvnetwork_ccd_dirs():
        path = os.path.join(ccd_dir, name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def _pvnetwork_disconnect(name: str) -> None:
    for socket_path in _PVNETWORK_MGMT_SOCKETS:
        if not socket_path or not os.path.exists(socket_path):
            continue
        try:
            subprocess.run(
                ["socat", "-", f"UNIX-CONNECT:{socket_path}"],
                input=f"kill {name}\nquit\n",
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except Exception:
            pass
        return


def _pvnetwork_crl_target() -> str:
    try:
        with open(_PVNETWORK_SERVER_CONF, "r", encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                parts = raw.strip().split()
                if len(parts) >= 2 and parts[0] == "crl-verify":
                    value = parts[1]
                    if os.path.isabs(value):
                        return value
                    return os.path.join(os.path.dirname(_PVNETWORK_SERVER_CONF), value)
    except OSError:
        pass
    return "/etc/openvpn/server/crl.pem"


def _pvnetwork_valid_cert_exists(name: str) -> bool:
    index = os.path.join(_PVNETWORK_EASYRSA_DIR, "pki", "index.txt")
    cn_pattern = re.compile(r"(?:^|/)CN=" + re.escape(name) + r"(?:/|$)")
    try:
        with open(index, "r", encoding="utf-8", errors="ignore") as handle:
            for raw in handle:
                if raw.startswith("V\t"):
                    subject = raw.rstrip("\r\n").split("\t")[-1]
                    if cn_pattern.search(subject):
                        return True
    except OSError:
        return False
    return False


def _pvnetwork_remove_pki_artifacts(name: str) -> None:
    pki = os.path.join(_PVNETWORK_EASYRSA_DIR, "pki")
    for relative in (
        f"issued/{name}.crt",
        f"private/{name}.key",
        f"reqs/{name}.req",
        f"inline/private/{name}.inline",
    ):
        path = os.path.join(pki, relative)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def _pvnetwork_publish_crl() -> bool:
    source = os.path.join(_PVNETWORK_EASYRSA_DIR, "pki", "crl.pem")
    target = _pvnetwork_crl_target()
    if not os.path.isfile(source):
        return False
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".pvnetwork.tmp"
    try:
        old = os.stat(target) if os.path.exists(target) else None
        with open(source, "rb") as src, open(tmp, "wb") as dst:
            dst.write(src.read())
        if old is not None:
            os.chmod(tmp, old.st_mode & 0o777)
            try:
                os.chown(tmp, old.st_uid, old.st_gid)
            except PermissionError:
                pass
        else:
            os.chmod(tmp, 0o644)
        os.replace(tmp, target)
        return True
    except OSError:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False


def _pvnetwork_revoke_certificate(name: str) -> bool | str:
    if not _pvnetwork_valid_cert_exists(name):
        return "not_found"
    easyrsa = os.path.join(_PVNETWORK_EASYRSA_DIR, "easyrsa")
    if not os.path.isfile(easyrsa):
        logger.error("EasyRSA missing: %s", easyrsa)
        return False
    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    env["EASYRSA_BATCH"] = "1"
    for command in (
        [easyrsa, "--batch", "revoke", name],
        [easyrsa, "--batch", "gen-crl"],
    ):
        try:
            result = subprocess.run(
                command,
                cwd=_PVNETWORK_EASYRSA_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.error("EasyRSA operation failed for %s: %s", name, exc)
            return False
        if result.returncode != 0:
            logger.error("EasyRSA operation failed for %s: %s", name, (result.stdout or "")[-1500:])
            return False
    return True if _pvnetwork_publish_crl() else False


def delete_user_on_server(name) -> bool | str:
    name = str(name or "").strip()
    if not _safe_name(name):
        return False
    _pvnetwork_remove_ccd(name)
    _pvnetwork_disconnect(name)
    result = _pvnetwork_revoke_certificate(name)
    if result is True:
        _pvnetwork_remove_pki_artifacts(name)
    try:
        profile = f"/root/{name}.ovpn"
        if os.path.exists(profile):
            os.remove(profile)
    except OSError:
        pass
    return result


def change_user_status(name: str, status: str) -> bool:
    name = str(name or "").strip()
    if not _safe_name(name):
        return False
    try:
        if status == "deactivate":
            _pvnetwork_remove_ccd(name)
            _pvnetwork_disconnect(name)
            return True
        if status == "activate":
            _pvnetwork_touch_ccd(name)
            return True
        return False
    except Exception as exc:
        logger.error("Status change failed for %s: %s", name, exc)
        return False


def restart_openvpn_service() -> bool:
    # Compatibility shim only. Per-user lifecycle must never restart the whole service.
    logger.info("Per-user lifecycle uses CCD/management socket; OpenVPN restart skipped")
    return True
'''


def install_user_lifecycle(root: Path) -> None:
    user_file = root / "core/service/user_managment.py"
    if not user_file.exists():
        raise SystemExit("USER_MANAGEMENT_NOT_FOUND")
    source = user_file.read_text(encoding="utf-8", errors="replace")
    marker = "# PVNETWORK_USER_LIFECYCLE_NO_RESTART_V1"
    start = source.find(marker)
    if start < 0:
        start = source.find("def delete_user_on_server")
    end = source.find("async def download_ovpn_file", start)
    if start < 0 or end < 0:
        raise SystemExit("USER_LIFECYCLE_MARKERS_NOT_FOUND")
    patched = source[:start] + USER_LIFECYCLE_NO_RESTART + "\n\n" + source[end:]
    user_file.write_text(patched, encoding="utf-8")


def install_router_openvpn_module(root: Path) -> None:
    router_file = root / "core/routers/router.py"
    module_file = root / "core/routers/router_openvpn.py"
    if not router_file.exists():
        raise SystemExit("ROUTER_NOT_FOUND")
    module_file.write_text(ROUTER_OPENVPN_MODULE, encoding="utf-8")
    source = router_file.read_text(encoding="utf-8", errors="replace")
    if "/router-openvpn/status" in source or "PVNETWORK_ROUTER_OPENVPN_INCLUDE_V1" in source:
        return
    source = source.rstrip() + '''

# PVNETWORK_ROUTER_OPENVPN_INCLUDE_V1
from core.routers.router_openvpn import router as router_openvpn_router
router.include_router(router_openvpn_router)
'''
    router_file.write_text(source, encoding="utf-8")


def ensure_line(path: Path, line: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if line not in {x.strip() for x in text.splitlines()}:
        path.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="/opt/ov-node")
    ap.add_argument("--router-only", action="store_true")
    ap.add_argument("--user-lifecycle-only", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)
    user_file = root / "core/service/user_managment.py"
    router_file = root / "core/routers/router.py"
    if not router_file.exists():
        raise SystemExit("OV-Node source layout not found")
    if args.user_lifecycle_only:
        install_user_lifecycle(root)
        print("PVNetwork user lifecycle no-restart patch applied")
        return 0
    if args.router_only:
        install_router_openvpn_module(root)
        print("PVNetwork router OpenVPN capability patch applied")
        return 0
    if not user_file.exists():
        raise SystemExit("OV-Node source layout not found")
    user_file.write_text(USER_MANAGEMENT, encoding="utf-8")
    install_user_lifecycle(root)
    router_file.write_text(ROUTER, encoding="utf-8")
    install_router_openvpn_module(root)

    print("PVNetwork node compatibility patch applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
