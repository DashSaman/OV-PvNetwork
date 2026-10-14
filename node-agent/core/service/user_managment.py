import re
import os
import subprocess
import csv
from pathlib import Path

from core.service.client_profile import verify_profile

from core.logger import logger
from core.config import settings
from core.schema.all_schemas import UsersUsage


def create_user_on_server(name) -> bool:
    name = str(name or "").strip()
    if not _pvnetwork_safe_name(name):
        return False
    try:
        versioned_builder = Path(__file__).resolve().parents[2] / 'resources/pvnetwork-build-client-profile'
        command = ['/usr/bin/bash', str(versioned_builder), name] if versioned_builder.is_file() else ["/usr/local/sbin/pvnetwork-build-client-profile", name]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=240, check=False,
        )
        path = os.path.join(_PVNETWORK_PROFILE_DIR, name+'.ovpn')
        if result.returncode != 0: return False
        verify_profile(Path(path), name, Path(_PVNETWORK_EASYRSA_DIR)/'pki')
        return True
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        logger.error("Verified profile generation failed")
        return False


# PVNETWORK_USER_LIFECYCLE_NO_RESTART_V1
import os
import re
import subprocess


def _pvnetwork_safe_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(name or "")))


_PVNETWORK_SERVER_CONF = os.getenv("PVNETWORK_OPENVPN_SERVER_CONF", "/etc/openvpn/server/server.conf")
_PVNETWORK_EASYRSA_DIR = os.getenv("PVNETWORK_EASYRSA_DIR", "/etc/openvpn/server/easy-rsa")
_PVNETWORK_MGMT_SOCKETS = (
    settings.openvpn_management_socket,
    "/run/openvpn/ov-management.sock",
    "/var/run/openvpn-server/server.sock",
)
_PVNETWORK_STATUS_LOG = os.getenv("PVNETWORK_OPENVPN_STATUS_LOG", "/var/log/openvpn/status.log")
_PVNETWORK_PROFILE_DIR = os.getenv("PVNETWORK_PROFILE_DIR", "/root")


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


def _pvnetwork_exact_cn_connected(name: str) -> bool:
    paths = (_PVNETWORK_STATUS_LOG, settings.openvpn_status_file)
    seen: set[str] = set()
    for path in paths:
        if not path or path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                for raw in handle:
                    if not raw.startswith("CLIENT_LIST,"):
                        continue
                    parts = raw.rstrip("\r\n").split(",")
                    if len(parts) >= 2 and parts[1] == name:
                        return True
        except OSError:
            continue
    return False


def get_user_identity_state(name: str) -> dict:
    name = str(name or "").strip()
    if not _pvnetwork_safe_name(name):
        return {
            "exists": False, "valid_certificate": False, "profile_exists": False,
            "ccd_enabled": False, "connected": False, "client_name": name,
            "capability_version": "pvn-user-identity-v1",
        }
    valid_certificate = _pvnetwork_valid_cert_exists(name)
    profile_exists = os.path.isfile(os.path.join(_PVNETWORK_PROFILE_DIR, f"{name}.ovpn"))
    ccd_enabled = any(os.path.isfile(os.path.join(path, name)) for path in _pvnetwork_ccd_dirs())
    connected = _pvnetwork_exact_cn_connected(name)
    return {
        "exists": bool(valid_certificate or profile_exists or ccd_enabled or connected),
        "valid_certificate": bool(valid_certificate),
        "profile_exists": bool(profile_exists),
        "ccd_enabled": bool(ccd_enabled),
        "connected": bool(connected),
        "client_name": name,
        "capability_version": "pvn-user-identity-v1",
    }


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
    had_valid_cert = _pvnetwork_valid_cert_exists(name)
    easyrsa = os.path.join(_PVNETWORK_EASYRSA_DIR, "easyrsa")
    if not os.path.isfile(easyrsa):
        logger.error("EasyRSA missing: %s", easyrsa)
        return False
    env = os.environ.copy()
    env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    env["EASYRSA_BATCH"] = "1"
    commands = []
    if had_valid_cert:
        commands.append([easyrsa, "--batch", "revoke", name])
    # Always regenerate/publish CRL so a retry repairs a prior revoke whose CRL publish failed.
    commands.append([easyrsa, "--batch", "gen-crl"])
    for command in commands:
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
    if not _pvnetwork_publish_crl():
        return False
    return True if had_valid_cert else "not_found"


def delete_user_on_server(name) -> bool | str:
    name = str(name or "").strip()
    if not _pvnetwork_safe_name(name):
        return False
    _pvnetwork_remove_ccd(name)
    _pvnetwork_disconnect(name)
    result = _pvnetwork_revoke_certificate(name)
    if result is not False:
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
    if not _pvnetwork_safe_name(name):
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


async def download_ovpn_file(name: str) -> str | None:
    """Return an existing profile or create it once."""
    if not _pvnetwork_safe_name(name):
        return None
    file_path = os.path.join(_PVNETWORK_PROFILE_DIR, name+'.ovpn')

    if os.path.lexists(file_path):
        try:
            verify_profile(Path(file_path), name, Path(_PVNETWORK_EASYRSA_DIR)/'pki')
            return file_path
        except (OSError, ValueError, UnicodeError):
            logger.error('Existing client profile identity verification failed')
            return None

    created = create_user_on_server(name)

    if not created:
        logger.error(
            f"Could not create OVPN profile for: {name}"
        )
        return None

    if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    logger.error(
        f"OVPN profile is still missing for: {name}"
    )
    return None

def get_users_usage() -> UsersUsage | None:
    if settings.accounting_file:
        from core.service.accounting import UsageLedger,status_samples
        ledger=UsageLedger(settings.accounting_file)
        ledger.consume_spool(settings.accounting_spool_dir)
        ledger.observe(status_samples(settings.openvpn_status_file))
        totals=ledger.totals()
        return UsersUsage(**totals) if totals['users'] else None
    users = {}
    users_rx = {}
    users_tx = {}
    file_path = settings.openvpn_status_file
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None

    for line in lines:
        line = line.strip()
        if line.startswith(("CLIENT_LIST,", "CLIENT_LIST\t")):
            parts = next(csv.reader([line], delimiter="\t" if "\t" in line else ","))
            if len(parts) < 7 or not _pvnetwork_safe_name(parts[1]):
                continue
            username = parts[1]
            try:
                bytes_received = int(parts[5])
                bytes_sent = int(parts[6])
            except ValueError:
                continue
            if bytes_received < 0 or bytes_sent < 0:
                continue
            total_bytes = bytes_received + bytes_sent
            users[username] = users.get(username, 0) + total_bytes
            # PVNETWORK_USERS_RX_TX_SPLIT_V1
            users_rx[username] = users_rx.get(username, 0) + bytes_received
            users_tx[username] = users_tx.get(username, 0) + bytes_sent

    if users:
        return UsersUsage(users=users, users_rx=users_rx, users_tx=users_tx)
    else:
        return None
