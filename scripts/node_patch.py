#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

USER_MANAGEMENT = r'''import os
import re
import subprocess

from core.logger import logger
from core.schema.all_schemas import UsersUsage

PROFILE_BUILDER = "/usr/local/sbin/ov-build-client-profile"
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
    # Kept for compatibility. OV-PvNetwork intentionally avoids routine OpenVPN restarts.
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
import os
import psutil

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
'''


def ensure_line(path: Path, line: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if line not in {x.strip() for x in text.splitlines()}:
        path.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="/opt/ov-node")
    args = ap.parse_args()
    root = Path(args.root)
    user_file = root / "core/service/user_managment.py"
    router_file = root / "core/routers/router.py"
    if not user_file.exists() or not router_file.exists():
        raise SystemExit("OV-Node source layout not found")
    user_file.write_text(USER_MANAGEMENT, encoding="utf-8")
    router_file.write_text(ROUTER, encoding="utf-8")

    server_conf = Path("/etc/openvpn/server/server.conf")
    ensure_line(server_conf, "client-config-dir ccd")
    ensure_line(server_conf, "ccd-exclusive")
    ensure_line(server_conf, "status /var/log/openvpn/status.log 10")
    ensure_line(server_conf, "status-version 2")
    print("OV-PvNetwork node compatibility patch applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
