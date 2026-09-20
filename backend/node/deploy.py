from __future__ import annotations

import base64
import ipaddress
import json
import os
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import paramiko

from backend.security_ssh import configure_ssh_client, sha256_fingerprint


DEPLOY_TIMEOUT = int(os.getenv("PVNETWORK_NODE_DEPLOY_TIMEOUT", "900"))
JOB_TTL = int(os.getenv("PVNETWORK_NODE_DEPLOY_JOB_TTL", "86400"))
JOB_DIR = Path(__file__).resolve().parents[2] / "data" / "deploy-jobs"
_jobs: dict[str, "DeployJob"] = {}
_jobs_lock = threading.RLock()
_host_locks: dict[str, threading.Lock] = {}


@dataclass
class DeployResult:
    address: str
    api_port: int
    api_key: str
    ovpn_port: int
    protocol: str
    fingerprint: str
    log: list[str]


@dataclass
class DeployJob:
    id: str
    host: str
    state: str = "queued"
    progress: int = 0
    stage: str = "queued"
    message: str = "Deployment queued"
    error: str | None = None
    result: dict | None = None
    logs: list[dict] = field(default_factory=list)
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))

    def public(self) -> dict:
        return asdict(self)


def _persist(job: DeployJob) -> None:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    tmp = JOB_DIR / f".{job.id}.tmp"
    target = JOB_DIR / f"{job.id}.json"
    tmp.write_text(json.dumps(job.public(), ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def _load_job(job_id: str) -> DeployJob | None:
    if not job_id or any(c not in "0123456789abcdef-" for c in job_id.lower()):
        return None
    path = JOB_DIR / f"{job_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return DeployJob(**data)
    except (OSError, ValueError, TypeError):
        return None


def get_deploy_job(job_id: str) -> dict | None:
    with _jobs_lock:
        live = _jobs.get(job_id)
        job = live or _load_job(job_id)
        if job and not live and job.state in {"queued", "running"}:
            job.state = "failed"
            job.error = "Deployment was interrupted by a backend restart; retry is safe"
            update_job(job, job.progress, "interrupted", job.error, "error")
        return job.public() if job else None


def new_deploy_job(host: str) -> DeployJob:
    cleanup_jobs()
    job = DeployJob(id=str(uuid.uuid4()), host=host)
    with _jobs_lock:
        _jobs[job.id] = job
        _persist(job)
    return job


def update_job(job: DeployJob, progress: int, stage: str, message: str,
               level: str = "info") -> None:
    with _jobs_lock:
        job.progress = max(job.progress, min(100, int(progress)))
        job.stage = stage
        job.message = message
        job.updated_at = int(time.time())
        job.logs.append({"time": job.updated_at, "stage": stage,
                         "level": level, "message": message[:1000]})
        job.logs = job.logs[-500:]
        _persist(job)


def finish_job(job: DeployJob, result: dict) -> None:
    with _jobs_lock:
        job.state = "succeeded"
        job.result = result
        job.error = None
        update_job(job, 100, "complete", "Node installed, verified and registered", "ok")


def fail_job(job: DeployJob, exc: Exception) -> None:
    message = str(exc).replace("\n", " ")[:1500]
    with _jobs_lock:
        job.state = "failed"
        job.error = message
        update_job(job, job.progress, "failed", message, "error")


def cleanup_jobs() -> None:
    cutoff = time.time() - JOB_TTL
    try:
        for path in JOB_DIR.glob("*.json"):
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
    except OSError:
        pass


def host_deploy_lock(host: str) -> threading.Lock:
    with _jobs_lock:
        return _host_locks.setdefault(host, threading.Lock())


def _valid_host(value: str) -> str:
    value = value.strip()
    try:
        ipaddress.ip_address(value)
    except ValueError:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
        if not value or len(value) > 253 or any(c not in allowed for c in value):
            raise ValueError("Invalid server address")
    return value


def _domain_payload(path: str) -> str:
    asset_root = os.getenv("PVNETWORK_DOMAIN_ASSET_ROOT")
    source = (
        Path(asset_root) / path.lstrip("/")
        if asset_root
        else Path(path)
    )

    try:
        return base64.b64encode(source.read_bytes()).decode("ascii")
    except OSError as exc:
        raise RuntimeError(
            f"Domain-history deployment asset is unavailable: {path}"
        ) from exc


def _router_capability_asset(relative_path: str) -> str:
    source = Path(__file__).resolve().parents[2] / relative_path
    try:
        return base64.b64encode(source.read_bytes()).decode("ascii")
    except OSError as exc:
        raise RuntimeError(
            f"Router OpenVPN deployment asset is unavailable: {relative_path}"
        ) from exc


def router_capability_install_script(node_root: str = "/opt/ov-node") -> str:
    """Return an idempotent Node-only capability installer; never starts a listener."""
    if node_root not in {"/opt/ov-node", '"$NEW"'}:
        raise ValueError("Unsupported node root expression")
    helper = _router_capability_asset("scripts/pvnetwork-router-openvpn")
    verifier = _router_capability_asset("scripts/pvnetwork-router-auth")
    patcher = _router_capability_asset("scripts/node_patch.py")
    router_py = f"{node_root}/core/routers/router.py"
    module_py = f"{node_root}/core/routers/router_openvpn.py"
    return f'''# PVNETWORK_ROUTER_CAPABILITY_V1
install -d -m 0755 /usr/local/sbin /usr/local/libexec
install -d -m 0700 /etc/pvnetwork/router-openvpn
echo '{helper}' | base64 -d >/usr/local/sbin/pvnetwork-router-openvpn.new
echo '{verifier}' | base64 -d >/usr/local/libexec/pvnetwork-router-auth.new
echo '{patcher}' | base64 -d >/tmp/pvnetwork-node-router-patch.py
chmod 0755 /usr/local/sbin/pvnetwork-router-openvpn.new /usr/local/libexec/pvnetwork-router-auth.new
python3 -m py_compile /tmp/pvnetwork-node-router-patch.py
python3 /tmp/pvnetwork-node-router-patch.py {node_root} --router-only
python3 -m py_compile {router_py} {module_py}
mv -f /usr/local/sbin/pvnetwork-router-openvpn.new /usr/local/sbin/pvnetwork-router-openvpn
mv -f /usr/local/libexec/pvnetwork-router-auth.new /usr/local/libexec/pvnetwork-router-auth
rm -f /tmp/pvnetwork-node-router-patch.py
# Capability files are inert until an explicit Router/OpenVPN enable API call.
'''


def _stage_script(api_port: int, ovpn_port: int, protocol: str,
                  api_key: str, panel_ip: str) -> str:
    proto_choice = "1" if protocol == "udp" else "2"
    domain_module = _domain_payload(
        "/opt/ov-node/core/routers/domain_history.py"
    )
    domain_collector = _domain_payload(
        "/usr/local/sbin/ov-domain-collector"
    )
    domain_unit = _domain_payload(
        "/etc/systemd/system/ov-domain-collector.service"
    )
    router_capability = router_capability_install_script('"$NEW"')
    return f'''#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
BACKUP="/opt/ov-node.backup.$(date +%s)"
NEW="/opt/ov-node.new.$$"
DOMAIN_BACKUP="/opt/ov-domain.backup.$(date +%s)"
changed=0
domain_changed=0
stage() {{ echo "PVNETWORK_STAGE|$1|$2|$3"; }}
retry() {{ local n=0; until "$@"; do n=$((n+1)); [[ $n -ge 3 ]] && return 1; sleep $((n*3)); done; }}
rollback() {{
  rc=$?
  rm -rf "$NEW" /tmp/ov-node.tar.gz
  if [[ $rc -ne 0 && $domain_changed -eq 1 ]]; then
    systemctl disable --now ov-domain-collector.service 2>/dev/null || true
    if [[ -f "$DOMAIN_BACKUP/collector" ]]; then
      install -m 750 "$DOMAIN_BACKUP/collector" /usr/local/sbin/ov-domain-collector
    else
      rm -f /usr/local/sbin/ov-domain-collector
    fi
    if [[ -f "$DOMAIN_BACKUP/unit" ]]; then
      install -m 644 "$DOMAIN_BACKUP/unit" /etc/systemd/system/ov-domain-collector.service
    else
      rm -f /etc/systemd/system/ov-domain-collector.service
    fi
    if [[ -f "$DOMAIN_BACKUP/default" ]]; then
      install -m 600 "$DOMAIN_BACKUP/default" /etc/default/ov-domain-collector
    else
      rm -f /etc/default/ov-domain-collector
    fi
    systemctl daemon-reload
    if grep -qx enabled "$DOMAIN_BACKUP/enabled" 2>/dev/null; then
      systemctl enable ov-domain-collector.service 2>/dev/null || true
    fi
    if grep -qx active "$DOMAIN_BACKUP/active" 2>/dev/null; then
      systemctl start ov-domain-collector.service 2>/dev/null || true
    fi
  fi
  if [[ $rc -ne 0 && $changed -eq 1 ]]; then
    systemctl stop ov-node 2>/dev/null || true
    rm -rf /opt/ov-node
    if [[ -d "$BACKUP" ]]; then
      mv "$BACKUP" /opt/ov-node
    fi
    systemctl daemon-reload
    if [[ -d /opt/ov-node ]]; then
      systemctl restart ov-node 2>/dev/null || true
    fi
    echo "PVNETWORK_ROLLBACK|Previous OV Node restored"
  fi
  rm -rf "$DOMAIN_BACKUP"
  exit $rc
}}
trap rollback EXIT
[[ $EUID -eq 0 ]] || {{ echo ROOT_REQUIRED; exit 20; }}
stage 5 preflight "Checking operating system and resources"
[[ -r /etc/os-release ]] || {{ echo "OS_RELEASE_NOT_FOUND"; exit 21; }}
. /etc/os-release
case "${{ID:-}}" in
  ubuntu|debian) ;;
  *) echo "UNSUPPORTED_OS:${{ID:-unknown}}:${{VERSION_ID:-unknown}}"; exit 21 ;;
esac
command -v apt-get >/dev/null 2>&1 || {{ echo "APT_NOT_AVAILABLE:${{ID:-unknown}}:${{VERSION_ID:-unknown}}"; exit 21; }}
[[ $(uname -m) =~ ^(x86_64|aarch64)$ ]] || {{ echo "UNSUPPORTED_ARCH:$(uname -m)"; exit 25; }}
[[ $(df -Pk /opt | awk 'NR==2{{print $4}}') -ge 2097152 ]] || {{ echo INSUFFICIENT_DISK; exit 26; }}
stage 12 packages "Updating repositories and installing packages"
retry apt-get update -y
retry apt-get install -y curl wget ca-certificates tar iptables iptables-persistent openvpn easy-rsa tcpdump
stage 25 runtime "Installing Python runtime"
if [[ ! -x /root/.local/bin/uv ]]; then retry curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh; sh /tmp/uv-install.sh; rm -f /tmp/uv-install.sh; fi
stage 35 openvpn "Installing pinned OpenVPN runtime"

OPENVPN_INSTALLER_URL="https://raw.githubusercontent.com/angristan/openvpn-install/ad22fd9eb0c8569a885f836ef6e37576d8702e9f/openvpn-install.sh"

retry curl -fL --connect-timeout 15 --max-time 120 "$OPENVPN_INSTALLER_URL" -o /root/openvpn-install.sh.new

chmod 700 /root/openvpn-install.sh.new

/root/openvpn-install.sh.new --help | grep -q 'Usage: openvpn-install <command>'

mv /root/openvpn-install.sh.new /root/openvpn-install.sh

if [[ ! -f /etc/openvpn/server/server.conf ]]; then
  /root/openvpn-install.sh install --port {ovpn_port} --protocol {protocol} --dns cloudflare --client bootstrap
fi

[[ -s /etc/openvpn/server/server.conf ]] || {{ echo OPENVPN_SERVER_CONF_MISSING; exit 27; }}

SERVER_CONF="/etc/openvpn/server/server.conf"

if grep -qE '^[[:space:]]*status[[:space:]]+' "$SERVER_CONF"; then
  sed -i -E 's#^[[:space:]]*status[[:space:]].*#status /var/log/openvpn-status.log 10#' "$SERVER_CONF"
else
  echo 'status /var/log/openvpn-status.log 10' >> "$SERVER_CONF"
fi

if grep -qE '^[[:space:]]*status-version[[:space:]]+' "$SERVER_CONF"; then
  sed -i -E 's/^[[:space:]]*status-version[[:space:]].*/status-version 2/' "$SERVER_CONF"
else
  echo 'status-version 2' >> "$SERVER_CONF"
fi

touch /var/log/openvpn-status.log
chmod 644 /var/log/openvpn-status.log

systemctl daemon-reload
systemctl enable openvpn-server@server.service >/dev/null 2>&1 || true
systemctl restart openvpn-server@server.service 2>/dev/null || systemctl restart openvpn

systemctl is-active --quiet openvpn-server@server.service || systemctl is-active --quiet openvpn

stage 42 openvpn_verified "OpenVPN server verified"

stage 50 download "Downloading pinned OV Node release"

rm -rf "$NEW"
mkdir -p "$NEW"

DOWNLOAD_URL="https://api.github.com/repos/primeZdev/ov-node/tarball/v1.3.6"

retry curl -fL --connect-timeout 15 --max-time 180 "$DOWNLOAD_URL" -o /tmp/ov-node.tar.gz

tar -tzf /tmp/ov-node.tar.gz >/dev/null

tar -xzf /tmp/ov-node.tar.gz -C "$NEW" --strip-components=1

cat >"$NEW/.env" <<EOF
SERVICE_PORT={api_port}
API_KEY={api_key}
EOF

sed -i 's/host="127.0.0.1"/host="0.0.0.0"/' "$NEW/main.py"

echo 'ZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCmltcG9ydCByZQppbXBvcnQgc3lzCgpyb290ID0gUGF0aChzeXMuYXJndlsxXSkKCnVzZXJfZmlsZSA9IHJvb3QgLyAiY29yZS9zZXJ2aWNlL3VzZXJfbWFuYWdtZW50LnB5Igpyb3V0ZXJfZmlsZSA9IHJvb3QgLyAiY29yZS9yb3V0ZXJzL3JvdXRlci5weSIKCmlmIG5vdCB1c2VyX2ZpbGUuZXhpc3RzKCk6CiAgICByYWlzZSBTeXN0ZW1FeGl0KCJVU0VSX01BTkFHRU1FTlRfTk9UX0ZPVU5EIikKCmlmIG5vdCByb3V0ZXJfZmlsZS5leGlzdHMoKToKICAgIHJhaXNlIFN5c3RlbUV4aXQoIlJPVVRFUl9OT1RfRk9VTkQiKQoKCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CiMgVVNFUiBNQU5BR0VNRU5UCiMgVXNlIHBpbm5lZCBvcGVudnBuLWluc3RhbGwgQ0xJIGluc3RlYWQgb2YgaW50ZXJuYWwgRWFzeVJTQSBwYXRocy4KIyA9PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0KCnMgPSB1c2VyX2ZpbGUucmVhZF90ZXh0KAogICAgZW5jb2Rpbmc9InV0Zi04IiwKICAgIGVycm9ycz0icmVwbGFjZSIsCikKCmZvciByZXF1aXJlZF9pbXBvcnQgaW4gKAogICAgImltcG9ydCBvcyIsCiAgICAiaW1wb3J0IHJlIiwKICAgICJpbXBvcnQgc3VicHJvY2VzcyIsCik6CiAgICBpZiByZXF1aXJlZF9pbXBvcnQgbm90IGluIHM6CiAgICAgICAgcyA9IHJlcXVpcmVkX2ltcG9ydCArICJcbiIgKyBzCgoKY3JlYXRlX3N0YXJ0ID0gcy5maW5kKAogICAgImRlZiBjcmVhdGVfdXNlcl9vbl9zZXJ2ZXIiCikKCmRlbGV0ZV9zdGFydCA9IHMuZmluZCgKICAgICJcbmRlZiBkZWxldGVfdXNlcl9vbl9zZXJ2ZXIiLAogICAgY3JlYXRlX3N0YXJ0LAopCgpjaGFuZ2Vfc3RhcnQgPSBzLmZpbmQoCiAgICAiXG5kZWYgY2hhbmdlX3VzZXJfc3RhdHVzIiwKICAgIGRlbGV0ZV9zdGFydCwKKQoKaWYgbWluKAogICAgY3JlYXRlX3N0YXJ0LAogICAgZGVsZXRlX3N0YXJ0LAogICAgY2hhbmdlX3N0YXJ0LAopIDwgMDoKICAgIHJhaXNlIFN5c3RlbUV4aXQoCiAgICAgICAgIlVTRVJfRlVOQ1RJT05fTUFSS0VSU19OT1RfRk9VTkQiCiAgICApCgoKbmV3X2NyZWF0ZSA9IHInJydkZWYgY3JlYXRlX3VzZXJfb25fc2VydmVyKG5hbWUpIC0+IGJvb2w6CiAgICB0cnk6CiAgICAgICAgbmFtZSA9IHN0cihuYW1lKS5zdHJpcCgpCgogICAgICAgIHNhZmVfbmFtZSA9IHJlLnN1YigKICAgICAgICAgICAgciJbXjAtOUEtWmEtel8tXSIsCiAgICAgICAgICAgICJfIiwKICAgICAgICAgICAgbmFtZSwKICAgICAgICApCgogICAgICAgIGlmICgKICAgICAgICAgICAgbm90IG5hbWUKICAgICAgICAgICAgb3Igc2FmZV9uYW1lICE9IG5hbWUKICAgICAgICAgICAgb3IgbGVuKG5hbWUpID4gNjQKICAgICAgICApOgogICAgICAgICAgICBsb2dnZXIuZXJyb3IoCiAgICAgICAgICAgICAgICAiSW52YWxpZCBPcGVuVlBOIGNsaWVudCBuYW1lOiAlcyIsCiAgICAgICAgICAgICAgICBuYW1lLAogICAgICAgICAgICApCiAgICAgICAgICAgIHJldHVybiBGYWxzZQoKICAgICAgICBpbnN0YWxsZXIgPSAiL3Jvb3Qvb3BlbnZwbi1pbnN0YWxsLnNoIgogICAgICAgIHByb2ZpbGVfZmlsZSA9ICIvcm9vdC8lcy5vdnBuIiAlIG5hbWUKCiAgICAgICAgY2NkX2RpciA9ICIvZXRjL29wZW52cG4vY2NkIgogICAgICAgIGNjZF9maWxlID0gIiVzLyVzIiAlICgKICAgICAgICAgICAgY2NkX2RpciwKICAgICAgICAgICAgbmFtZSwKICAgICAgICApCgogICAgICAgIG9zLm1ha2VkaXJzKAogICAgICAgICAgICBjY2RfZGlyLAogICAgICAgICAgICBleGlzdF9vaz1UcnVlLAogICAgICAgICkKCiAgICAgICAgaWYgKAogICAgICAgICAgICBvcy5wYXRoLmlzZmlsZShwcm9maWxlX2ZpbGUpCiAgICAgICAgICAgIGFuZCBvcy5wYXRoLmdldHNpemUocHJvZmlsZV9maWxlKSA+IDIwMAogICAgICAgICk6CiAgICAgICAgICAgIG9wZW4oCiAgICAgICAgICAgICAgICBjY2RfZmlsZSwKICAgICAgICAgICAgICAgICJhIiwKICAgICAgICAgICAgKS5jbG9zZSgpCgogICAgICAgICAgICBvcy5jaG1vZCgKICAgICAgICAgICAgICAgIGNjZF9maWxlLAogICAgICAgICAgICAgICAgMG82NDQsCiAgICAgICAgICAgICkKCiAgICAgICAgICAgIHJldHVybiBUcnVlCgogICAgICAgIGlmIG5vdCBvcy5wYXRoLmlzZmlsZShpbnN0YWxsZXIpOgogICAgICAgICAgICBsb2dnZXIuZXJyb3IoCiAgICAgICAgICAgICAgICAiT3BlblZQTiBpbnN0YWxsZXIgQ0xJIGlzIG1pc3NpbmciCiAgICAgICAgICAgICkKICAgICAgICAgICAgcmV0dXJuIEZhbHNlCgogICAgICAgIGVudiA9IG9zLmVudmlyb24uY29weSgpCgogICAgICAgIGVudlsiUEFUSCJdID0gKAogICAgICAgICAgICAiL3Vzci9sb2NhbC9zYmluOiIKICAgICAgICAgICAgIi91c3IvbG9jYWwvYmluOiIKICAgICAgICAgICAgIi91c3Ivc2JpbjoiCiAgICAgICAgICAgICIvdXNyL2JpbjoiCiAgICAgICAgICAgICIvc2JpbjoiCiAgICAgICAgICAgICIvYmluIgogICAgICAgICkKCiAgICAgICAgcmVzdWx0ID0gc3VicHJvY2Vzcy5ydW4oCiAgICAgICAgICAgIFsKICAgICAgICAgICAgICAgIGluc3RhbGxlciwKICAgICAgICAgICAgICAgICJjbGllbnQiLAogICAgICAgICAgICAgICAgImFkZCIsCiAgICAgICAgICAgICAgICBuYW1lLAogICAgICAgICAgICAgICAgIi0tb3V0cHV0IiwKICAgICAgICAgICAgICAgIHByb2ZpbGVfZmlsZSwKICAgICAgICAgICAgXSwKICAgICAgICAgICAgZW52PWVudiwKICAgICAgICAgICAgc3Rkb3V0PXN1YnByb2Nlc3MuUElQRSwKICAgICAgICAgICAgc3RkZXJyPXN1YnByb2Nlc3MuU1RET1VULAogICAgICAgICAgICB0ZXh0PVRydWUsCiAgICAgICAgICAgIGNoZWNrPUZhbHNlLAogICAgICAgICAgICB0aW1lb3V0PTE4MCwKICAgICAgICApCgogICAgICAgIGlmIHJlc3VsdC5yZXR1cm5jb2RlICE9IDA6CiAgICAgICAgICAgIGxvZ2dlci5lcnJvcigKICAgICAgICAgICAgICAgICJPcGVuVlBOIENMSSBjbGllbnQgYWRkIGZhaWxlZCBmb3IgJXM6ICVzIiwKICAgICAgICAgICAgICAgIG5hbWUsCiAgICAgICAgICAgICAgICAocmVzdWx0LnN0ZG91dCBvciAiIilbLTE1MDA6XSwKICAgICAgICAgICAgKQogICAgICAgICAgICByZXR1cm4gRmFsc2UKCiAgICAgICAgaWYgKAogICAgICAgICAgICBub3Qgb3MucGF0aC5pc2ZpbGUocHJvZmlsZV9maWxlKQogICAgICAgICAgICBvciBvcy5wYXRoLmdldHNpemUocHJvZmlsZV9maWxlKSA8PSAyMDAKICAgICAgICApOgogICAgICAgICAgICBsb2dnZXIuZXJyb3IoCiAgICAgICAgICAgICAgICAiT1ZQTiBwcm9maWxlIG1pc3NpbmcgYWZ0ZXIgY2xpZW50IGNyZWF0aW9uOiAlcyIsCiAgICAgICAgICAgICAgICBuYW1lLAogICAgICAgICAgICApCiAgICAgICAgICAgIHJldHVybiBGYWxzZQoKICAgICAgICBvcy5jaG1vZCgKICAgICAgICAgICAgcHJvZmlsZV9maWxlLAogICAgICAgICAgICAwbzYwMCwKICAgICAgICApCgogICAgICAgIG9wZW4oCiAgICAgICAgICAgIGNjZF9maWxlLAogICAgICAgICAgICAiYSIsCiAgICAgICAgKS5jbG9zZSgpCgogICAgICAgIG9zLmNobW9kKAogICAgICAgICAgICBjY2RfZmlsZSwKICAgICAgICAgICAgMG82NDQsCiAgICAgICAgKQoKICAgICAgICBsb2dnZXIuaW5mbygKICAgICAgICAgICAgIk9wZW5WUE4gdXNlciBjcmVhdGVkIHN1Y2Nlc3NmdWxseTogJXMiLAogICAgICAgICAgICBuYW1lLAogICAgICAgICkKCiAgICAgICAgcmV0dXJuIFRydWUKCiAgICBleGNlcHQgc3VicHJvY2Vzcy5UaW1lb3V0RXhwaXJlZDoKICAgICAgICBsb2dnZXIuZXJyb3IoCiAgICAgICAgICAgICJUaW1lb3V0IHdoaWxlIGNyZWF0aW5nIE9wZW5WUE4gdXNlcjogJXMiLAogICAgICAgICAgICBuYW1lLAogICAgICAgICkKICAgICAgICByZXR1cm4gRmFsc2UKCiAgICBleGNlcHQgRXhjZXB0aW9uIGFzIGV4YzoKICAgICAgICBsb2dnZXIuZXJyb3IoCiAgICAgICAgICAgICJGYWlsZWQgdG8gY3JlYXRlIE9wZW5WUE4gdXNlciAlczogJXMiLAogICAgICAgICAgICBuYW1lLAogICAgICAgICAgICBleGMsCiAgICAgICAgKQogICAgICAgIHJldHVybiBGYWxzZQonJycKCgpuZXdfZGVsZXRlID0gcicnJ2RlZiBkZWxldGVfdXNlcl9vbl9zZXJ2ZXIobmFtZSkgLT4gYm9vbCB8IHN0cjoKICAgIHRyeToKICAgICAgICBuYW1lID0gc3RyKG5hbWUpLnN0cmlwKCkKCiAgICAgICAgc2FmZV9uYW1lID0gcmUuc3ViKAogICAgICAgICAgICByIlteMC05QS1aYS16Xy1dIiwKICAgICAgICAgICAgIl8iLAogICAgICAgICAgICBuYW1lLAogICAgICAgICkKCiAgICAgICAgaWYgKAogICAgICAgICAgICBub3QgbmFtZQogICAgICAgICAgICBvciBzYWZlX25hbWUgIT0gbmFtZQogICAgICAgICk6CiAgICAgICAgICAgIHJldHVybiBGYWxzZQoKICAgICAgICBpbnN0YWxsZXIgPSAiL3Jvb3Qvb3BlbnZwbi1pbnN0YWxsLnNoIgoKICAgICAgICBwcm9maWxlX2ZpbGUgPSAiL3Jvb3QvJXMub3ZwbiIgJSBuYW1lCiAgICAgICAgY2NkX2ZpbGUgPSAiL2V0Yy9vcGVudnBuL2NjZC8lcyIgJSBuYW1lCgogICAgICAgIHJlc3VsdCA9IE5vbmUKCiAgICAgICAgaWYgb3MucGF0aC5pc2ZpbGUoaW5zdGFsbGVyKToKICAgICAgICAgICAgZW52ID0gb3MuZW52aXJvbi5jb3B5KCkKCiAgICAgICAgICAgIGVudlsiUEFUSCJdID0gKAogICAgICAgICAgICAgICAgIi91c3IvbG9jYWwvc2JpbjoiCiAgICAgICAgICAgICAgICAiL3Vzci9sb2NhbC9iaW46IgogICAgICAgICAgICAgICAgIi91c3Ivc2JpbjoiCiAgICAgICAgICAgICAgICAiL3Vzci9iaW46IgogICAgICAgICAgICAgICAgIi9zYmluOiIKICAgICAgICAgICAgICAgICIvYmluIgogICAgICAgICAgICApCgogICAgICAgICAgICByZXN1bHQgPSBzdWJwcm9jZXNzLnJ1bigKICAgICAgICAgICAgICAgIFsKICAgICAgICAgICAgICAgICAgICBpbnN0YWxsZXIsCiAgICAgICAgICAgICAgICAgICAgImNsaWVudCIsCiAgICAgICAgICAgICAgICAgICAgInJldm9rZSIsCiAgICAgICAgICAgICAgICAgICAgbmFtZSwKICAgICAgICAgICAgICAgICAgICAiLS1mb3JjZSIsCiAgICAgICAgICAgICAgICBdLAogICAgICAgICAgICAgICAgZW52PWVudiwKICAgICAgICAgICAgICAgIHN0ZG91dD1zdWJwcm9jZXNzLlBJUEUsCiAgICAgICAgICAgICAgICBzdGRlcnI9c3VicHJvY2Vzcy5TVERPVVQsCiAgICAgICAgICAgICAgICB0ZXh0PVRydWUsCiAgICAgICAgICAgICAgICBjaGVjaz1GYWxzZSwKICAgICAgICAgICAgICAgIHRpbWVvdXQ9MTgwLAogICAgICAgICAgICApCgogICAgICAgIGZvciBwYXRoIGluICgKICAgICAgICAgICAgcHJvZmlsZV9maWxlLAogICAgICAgICAgICBjY2RfZmlsZSwKICAgICAgICApOgogICAgICAgICAgICB0cnk6CiAgICAgICAgICAgICAgICBpZiBvcy5wYXRoLmV4aXN0cyhwYXRoKToKICAgICAgICAgICAgICAgICAgICBvcy5yZW1vdmUocGF0aCkKICAgICAgICAgICAgZXhjZXB0IE9TRXJyb3I6CiAgICAgICAgICAgICAgICBwYXNzCgogICAgICAgIGlmIHJlc3VsdCBpcyBOb25lOgogICAgICAgICAgICByZXR1cm4gRmFsc2UKCiAgICAgICAgaWYgcmVzdWx0LnJldHVybmNvZGUgPT0gMDoKICAgICAgICAgICAgcmV0dXJuIFRydWUKCiAgICAgICAgb3V0cHV0ID0gKAogICAgICAgICAgICByZXN1bHQuc3Rkb3V0IG9yICIiCiAgICAgICAgKS5sb3dlcigpCgogICAgICAgIGlmIGFueSgKICAgICAgICAgICAgdG9rZW4gaW4gb3V0cHV0CiAgICAgICAgICAgIGZvciB0b2tlbiBpbiAoCiAgICAgICAgICAgICAgICAibm90IGZvdW5kIiwKICAgICAgICAgICAgICAgICJkb2VzIG5vdCBleGlzdCIsCiAgICAgICAgICAgICAgICAiYWxyZWFkeSByZXZva2VkIiwKICAgICAgICAgICAgICAgICJubyBjbGllbnQiLAogICAgICAgICAgICApCiAgICAgICAgKToKICAgICAgICAgICAgcmV0dXJuICJub3RfZm91bmQiCgogICAgICAgIGxvZ2dlci5lcnJvcigKICAgICAgICAgICAgIk9wZW5WUE4gQ0xJIHJldm9rZSBmYWlsZWQgZm9yICVzOiAlcyIsCiAgICAgICAgICAgIG5hbWUsCiAgICAgICAgICAgIChyZXN1bHQuc3Rkb3V0IG9yICIiKVstMTUwMDpdLAogICAgICAgICkKCiAgICAgICAgcmV0dXJuIEZhbHNlCgogICAgZXhjZXB0IHN1YnByb2Nlc3MuVGltZW91dEV4cGlyZWQ6CiAgICAgICAgcmV0dXJuIEZhbHNlCgogICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBleGM6CiAgICAgICAgbG9nZ2VyLmVycm9yKAogICAgICAgICAgICAiRGVsZXRlIHVzZXIgZmFpbGVkIGZvciAlczogJXMiLAogICAgICAgICAgICBuYW1lLAogICAgICAgICAgICBleGMsCiAgICAgICAgKQogICAgICAgIHJldHVybiBGYWxzZQonJycKCgpzID0gKAogICAgc1s6Y3JlYXRlX3N0YXJ0XQogICAgKyBuZXdfY3JlYXRlCiAgICArICJcblxuIgogICAgKyBuZXdfZGVsZXRlCiAgICArIHNbY2hhbmdlX3N0YXJ0Ol0KKQoKCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CiMgU0FGRSBVU0FHRQojIE1pc3Npbmcgc3RhdHVzIGxvZyBtdXN0IE5FVkVSIGNyYXNoIE9WLU5vZGUuCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09Cgp1c2FnZV9zdGFydCA9IHMuZmluZCgKICAgICJkZWYgZ2V0X3VzZXJzX3VzYWdlKCkiCikKCmlmIHVzYWdlX3N0YXJ0ID49IDA6CgogICAgdXNhZ2VfZW5kID0gcy5maW5kKAogICAgICAgICJcbmRlZiAiLAogICAgICAgIHVzYWdlX3N0YXJ0ICsgMTAsCiAgICApCgogICAgaWYgdXNhZ2VfZW5kIDwgMDoKICAgICAgICB1c2FnZV9lbmQgPSBsZW4ocykKCiAgICBuZXdfdXNhZ2UgPSByJycnZGVmIGdldF91c2Vyc191c2FnZSgpIC0+IFVzZXJzVXNhZ2UgfCBOb25lOgogICAgdXNlcnMgPSB7fQogICAgZmlsZV9wYXRoID0gIi92YXIvbG9nL29wZW52cG4tc3RhdHVzLmxvZyIKCiAgICBpZiBub3Qgb3MucGF0aC5pc2ZpbGUoZmlsZV9wYXRoKToKICAgICAgICByZXR1cm4gTm9uZQoKICAgIHRyeToKICAgICAgICB3aXRoIG9wZW4oCiAgICAgICAgICAgIGZpbGVfcGF0aCwKICAgICAgICAgICAgInIiLAogICAgICAgICAgICBlbmNvZGluZz0idXRmLTgiLAogICAgICAgICAgICBlcnJvcnM9Imlnbm9yZSIsCiAgICAgICAgKSBhcyBoYW5kbGU6CiAgICAgICAgICAgIGxpbmVzID0gaGFuZGxlLnJlYWRsaW5lcygpCiAgICBleGNlcHQgT1NFcnJvcjoKICAgICAgICByZXR1cm4gTm9uZQoKICAgIGZvciBsaW5lIGluIGxpbmVzOgogICAgICAgIGxpbmUgPSBsaW5lLnN0cmlwKCkKCiAgICAgICAgaWYgbm90IGxpbmUuc3RhcnRzd2l0aCgKICAgICAgICAgICAgIkNMSUVOVF9MSVNUIgogICAgICAgICk6CiAgICAgICAgICAgIGNvbnRpbnVlCgogICAgICAgIGlmIGxpbmUuc3RhcnRzd2l0aCgKICAgICAgICAgICAgIkNMSUVOVF9MSVNULENvbW1vbiBOYW1lIgogICAgICAgICk6CiAgICAgICAgICAgIGNvbnRpbnVlCgogICAgICAgIHBhcnRzID0gbGluZS5zcGxpdCgiLCIpCgogICAgICAgIGlmIGxlbihwYXJ0cykgPCA3OgogICAgICAgICAgICBjb250aW51ZQoKICAgICAgICB0cnk6CiAgICAgICAgICAgIHVzZXJuYW1lID0gcGFydHNbMV0KICAgICAgICAgICAgcnggPSBpbnQocGFydHNbNV0pCiAgICAgICAgICAgIHR4ID0gaW50KHBhcnRzWzZdKQogICAgICAgIGV4Y2VwdCAoCiAgICAgICAgICAgIFZhbHVlRXJyb3IsCiAgICAgICAgICAgIEluZGV4RXJyb3IsCiAgICAgICAgKToKICAgICAgICAgICAgY29udGludWUKCiAgICAgICAgdXNlcnNbdXNlcm5hbWVdID0gcnggKyB0eAoKICAgIGlmIHVzZXJzOgogICAgICAgIHJldHVybiBVc2Vyc1VzYWdlKAogICAgICAgICAgICB1c2Vycz11c2VycwogICAgICAgICkKCiAgICByZXR1cm4gTm9uZQonJycKCiAgICBzID0gKAogICAgICAgIHNbOnVzYWdlX3N0YXJ0XQogICAgICAgICsgbmV3X3VzYWdlCiAgICAgICAgKyBzW3VzYWdlX2VuZDpdCiAgICApCgoKdXNlcl9maWxlLndyaXRlX3RleHQoCiAgICBzLAogICAgZW5jb2Rpbmc9InV0Zi04IiwKKQoKCiMgPT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09CiMgUk9VVEVSIC8gTUVUUklDUyAvIE9OTElORSBVU0VSUwojID09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PQoKcyA9IHJvdXRlcl9maWxlLnJlYWRfdGV4dCgKICAgIGVuY29kaW5nPSJ1dGYtOCIsCiAgICBlcnJvcnM9InJlcGxhY2UiLAopCgoKIyBSZW1vdmUgb25seSBhbiBvcnBoYW4gb3B0aW9uYWwgZG9tYWluLWhpc3RvcnkgaW1wb3J0Lgpkb21haW5fbW9kdWxlID0gKAogICAgcm9vdAogICAgLyAiY29yZS9yb3V0ZXJzL2RvbWFpbl9oaXN0b3J5LnB5IgopCgppZiBub3QgZG9tYWluX21vZHVsZS5leGlzdHMoKToKCiAgICBzID0gcmUuc3ViKAogICAgICAgIHIiKD9tKV5bIFx0XSpmcm9tIGNvcmVcLnJvdXRlcnNcLmRvbWFpbl9oaXN0b3J5IGltcG9ydCByb3V0ZXIgYXMgZG9tYWluX2hpc3Rvcnlfcm91dGVyWyBcdF0qXG4/IiwKICAgICAgICAiIiwKICAgICAgICBzLAogICAgKQoKICAgIHMgPSByZS5zdWIoCiAgICAgICAgciIoP20pXlsgXHRdKnJvdXRlclwuaW5jbHVkZV9yb3V0ZXJcKGRvbWFpbl9oaXN0b3J5X3JvdXRlclwpWyBcdF0qXG4/IiwKICAgICAgICAiIiwKICAgICAgICBzLAogICAgKQoKCmlmIG5vdCByZS5zZWFyY2goCiAgICByIig/bSleaW1wb3J0IHRpbWVccyokIiwKICAgIHMsCik6CiAgICBsaW5lcyA9IHMuc3BsaXRsaW5lcygpCgogICAgaW5zZXJ0X2F0ID0gMAoKICAgIHdoaWxlICgKICAgICAgICBpbnNlcnRfYXQgPCBsZW4obGluZXMpCiAgICAgICAgYW5kIGxpbmVzW2luc2VydF9hdF0uc3RhcnRzd2l0aCgKICAgICAgICAgICAgImZyb20gX19mdXR1cmVfXyIKICAgICAgICApCiAgICApOgogICAgICAgIGluc2VydF9hdCArPSAxCgogICAgbGluZXMuaW5zZXJ0KAogICAgICAgIGluc2VydF9hdCwKICAgICAgICAiaW1wb3J0IHRpbWUiLAogICAgKQoKICAgIHMgPSAiXG4iLmpvaW4obGluZXMpICsgIlxuIgoKCiMgTm9ybWFsaXplIGhlbHBlciBhbGlhc2VzIGxlZnQgYnkgYW4gb2xkZXIgUFZOZXR3b3JrIG5vZGUgcGF0Y2guCmZvciBsZWdhY3lfYWxpYXMsIGN1cnJlbnRfYWxpYXMgaW4gKAogICAgKCJfb3ZfZGFzaGJvYXJkX2RlZmF1bHRfaW50ZXJmYWNlIiwgIl9wdm5ldHdvcmtfZGFzaGJvYXJkX2RlZmF1bHRfaW50ZXJmYWNlIiksCiAgICAoIl9vdl9kYXNoYm9hcmRfbmV0d29ya19zbmFwc2hvdCIsICJfcHZuZXR3b3JrX2Rhc2hib2FyZF9uZXR3b3JrX3NuYXBzaG90IiksCiAgICAoIl9vdl9vcGVudnBuX29ubGluZV9zbmFwc2hvdCIsICJfcHZuZXR3b3JrX29wZW52cG5fb25saW5lX3NuYXBzaG90IiksCik6CiAgICBzID0gcy5yZXBsYWNlKGxlZ2FjeV9hbGlhcywgY3VycmVudF9hbGlhcykKCgpzdGF0dXNfbWFya2VyID0gJ0Byb3V0ZXIuZ2V0KCIvc3RhdHVzIicKCnN0YXR1c19wb3MgPSBzLmZpbmQoCiAgICBzdGF0dXNfbWFya2VyCikKCmlmIHN0YXR1c19wb3MgPCAwOgogICAgcmFpc2UgU3lzdGVtRXhpdCgKICAgICAgICAiU1RBVFVTX1JPVVRFX05PVF9GT1VORCIKICAgICkKCgppZiAiZGVmIF9wdm5ldHdvcmtfZGFzaGJvYXJkX25ldHdvcmtfc25hcHNob3QiIG5vdCBpbiBzOgoKICAgIGhlbHBlciA9IHInJycKZGVmIF9wdm5ldHdvcmtfZGFzaGJvYXJkX2RlZmF1bHRfaW50ZXJmYWNlKCk6CiAgICB0cnk6CiAgICAgICAgd2l0aCBvcGVuKAogICAgICAgICAgICAiL3Byb2MvbmV0L3JvdXRlIiwKICAgICAgICAgICAgInIiLAogICAgICAgICAgICBlbmNvZGluZz0idXRmLTgiLAogICAgICAgICAgICBlcnJvcnM9Imlnbm9yZSIsCiAgICAgICAgKSBhcyBoYW5kbGU6CgogICAgICAgICAgICBmb3IgbGluZSBpbiBoYW5kbGUucmVhZGxpbmVzKClbMTpdOgogICAgICAgICAgICAgICAgcGFydHMgPSBsaW5lLnNwbGl0KCkKCiAgICAgICAgICAgICAgICBpZiAoCiAgICAgICAgICAgICAgICAgICAgbGVuKHBhcnRzKSA+IDEKICAgICAgICAgICAgICAgICAgICBhbmQgcGFydHNbMV0gPT0gIjAwMDAwMDAwIgogICAgICAgICAgICAgICAgKToKICAgICAgICAgICAgICAgICAgICByZXR1cm4gcGFydHNbMF0KCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCiAgICByZXR1cm4gTm9uZQoKCmRlZiBfcHZuZXR3b3JrX2Rhc2hib2FyZF9uZXR3b3JrX3NuYXBzaG90KCk6CiAgICBpbnRlcmZhY2UgPSAoCiAgICAgICAgX3B2bmV0d29ya19kYXNoYm9hcmRfZGVmYXVsdF9pbnRlcmZhY2UoKQogICAgKQoKICAgIHJlc3VsdCA9IHsKICAgICAgICAibmV0d29ya19pbnRlcmZhY2UiOgogICAgICAgICAgICBpbnRlcmZhY2UsCgogICAgICAgICJ1cHRpbWUiOgogICAgICAgICAgICBpbnQoCiAgICAgICAgICAgICAgICBtYXgoCiAgICAgICAgICAgICAgICAgICAgMCwKICAgICAgICAgICAgICAgICAgICB0aW1lLnRpbWUoKQogICAgICAgICAgICAgICAgICAgIC0gcHN1dGlsLmJvb3RfdGltZSgpLAogICAgICAgICAgICAgICAgKQogICAgICAgICAgICApLAoKICAgICAgICAiYm9vdF90aW1lIjoKICAgICAgICAgICAgaW50KAogICAgICAgICAgICAgICAgcHN1dGlsLmJvb3RfdGltZSgpCiAgICAgICAgICAgICksCgogICAgICAgICJyeF9ieXRlcyI6CiAgICAgICAgICAgIDAsCgogICAgICAgICJ0eF9ieXRlcyI6CiAgICAgICAgICAgIDAsCgogICAgICAgICJ0cmFmZmljX2J5dGVzIjoKICAgICAgICAgICAgMCwKICAgIH0KCiAgICBpZiBub3QgaW50ZXJmYWNlOgogICAgICAgIHJldHVybiByZXN1bHQKCiAgICBjb3VudGVycyA9IHBzdXRpbC5uZXRfaW9fY291bnRlcnMoCiAgICAgICAgcGVybmljPVRydWUKICAgICkKCiAgICBpbyA9IGNvdW50ZXJzLmdldCgKICAgICAgICBpbnRlcmZhY2UKICAgICkKCiAgICBpZiBpbyBpcyBOb25lOgogICAgICAgIHJldHVybiByZXN1bHQKCiAgICByeCA9IGludCgKICAgICAgICBpby5ieXRlc19yZWN2IG9yIDAKICAgICkKCiAgICB0eCA9IGludCgKICAgICAgICBpby5ieXRlc19zZW50IG9yIDAKICAgICkKCiAgICByZXN1bHQudXBkYXRlKAogICAgICAgIHsKICAgICAgICAgICAgInJ4X2J5dGVzIjoKICAgICAgICAgICAgICAgIHJ4LAoKICAgICAgICAgICAgInR4X2J5dGVzIjoKICAgICAgICAgICAgICAgIHR4LAoKICAgICAgICAgICAgInRyYWZmaWNfYnl0ZXMiOgogICAgICAgICAgICAgICAgcnggKyB0eCwKICAgICAgICB9CiAgICApCgogICAgcmV0dXJuIHJlc3VsdAoKCmRlZiBfcHZuZXR3b3JrX29wZW52cG5fb25saW5lX3NuYXBzaG90KCk6CiAgICBwYXRoID0gIi92YXIvbG9nL29wZW52cG4tc3RhdHVzLmxvZyIKCiAgICBjb21tb25fbmFtZXMgPSBzZXQoKQogICAgc2Vzc2lvbnMgPSAwCgogICAgaWYgbm90IFBhdGgocGF0aCkuaXNfZmlsZSgpOgogICAgICAgIHJldHVybiB7CiAgICAgICAgICAgICJvbmxpbmVfY291bnQiOiAwLAogICAgICAgICAgICAib25saW5lX3Nlc3Npb25zIjogMCwKICAgICAgICAgICAgIm9wZW52cG5fc3RhdHVzX2ZpbGUiOiBwYXRoLAogICAgICAgIH0KCiAgICB0cnk6CiAgICAgICAgd2l0aCBvcGVuKAogICAgICAgICAgICBwYXRoLAogICAgICAgICAgICAiciIsCiAgICAgICAgICAgIGVuY29kaW5nPSJ1dGYtOCIsCiAgICAgICAgICAgIGVycm9ycz0iaWdub3JlIiwKICAgICAgICApIGFzIGhhbmRsZToKCiAgICAgICAgICAgIGZvciByYXcgaW4gaGFuZGxlOgogICAgICAgICAgICAgICAgaWYgbm90IHJhdy5zdGFydHN3aXRoKAogICAgICAgICAgICAgICAgICAgICJDTElFTlRfTElTVCwiCiAgICAgICAgICAgICAgICApOgogICAgICAgICAgICAgICAgICAgIGNvbnRpbnVlCgogICAgICAgICAgICAgICAgcGFydHMgPSByYXcucnN0cmlwKAogICAgICAgICAgICAgICAgICAgICJcclxuIgogICAgICAgICAgICAgICAgKS5zcGxpdCgiLCIpCgogICAgICAgICAgICAgICAgaWYgbGVuKHBhcnRzKSA8IDI6CiAgICAgICAgICAgICAgICAgICAgY29udGludWUKCiAgICAgICAgICAgICAgICBjb21tb25fbmFtZSA9ICgKICAgICAgICAgICAgICAgICAgICBwYXJ0c1sxXS5zdHJpcCgpCiAgICAgICAgICAgICAgICApCgogICAgICAgICAgICAgICAgaWYgY29tbW9uX25hbWUgPT0gIkNvbW1vbiBOYW1lIjoKICAgICAgICAgICAgICAgICAgICBjb250aW51ZQoKICAgICAgICAgICAgICAgIHNlc3Npb25zICs9IDEKCiAgICAgICAgICAgICAgICBpZiAoCiAgICAgICAgICAgICAgICAgICAgY29tbW9uX25hbWUKICAgICAgICAgICAgICAgICAgICBhbmQgY29tbW9uX25hbWUgIT0gIlVOREVGIgogICAgICAgICAgICAgICAgKToKICAgICAgICAgICAgICAgICAgICBjb21tb25fbmFtZXMuYWRkKAogICAgICAgICAgICAgICAgICAgICAgICBjb21tb25fbmFtZQogICAgICAgICAgICAgICAgICAgICkKCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCiAgICByZXR1cm4gewogICAgICAgICJvbmxpbmVfY291bnQiOgogICAgICAgICAgICBsZW4oY29tbW9uX25hbWVzKSwKCiAgICAgICAgIm9ubGluZV9zZXNzaW9ucyI6CiAgICAgICAgICAgIHNlc3Npb25zLAoKICAgICAgICAib3BlbnZwbl9zdGF0dXNfZmlsZSI6CiAgICAgICAgICAgIHBhdGgsCiAgICB9CgoKJycnCgogICAgcyA9ICgKICAgICAgICBzWzpzdGF0dXNfcG9zXQogICAgICAgICsgaGVscGVyCiAgICAgICAgKyBzW3N0YXR1c19wb3M6XQogICAgKQoKCnN0YXR1c19wb3MgPSBzLmZpbmQoCiAgICBzdGF0dXNfbWFya2VyCikKCnVzYWdlX3JvdXRlID0gcy5maW5kKAogICAgJ0Byb3V0ZXIuZ2V0KCIvdXNhZ2UiJywKICAgIHN0YXR1c19wb3MsCikKCmlmIHVzYWdlX3JvdXRlIDwgMDoKICAgIHJhaXNlIFN5c3RlbUV4aXQoCiAgICAgICAgIlVTQUdFX1JPVVRFX05PVF9GT1VORCIKICAgICkKCmJsb2NrID0gc1sKICAgIHN0YXR1c19wb3M6dXNhZ2Vfcm91dGUKXQoKaW5zZXJ0aW9ucyA9IFtdCgppZiAoCiAgICAiX3B2bmV0d29ya19kYXNoYm9hcmRfbmV0d29ya19zbmFwc2hvdCgpIgogICAgbm90IGluIGJsb2NrCik6CiAgICBpbnNlcnRpb25zLmFwcGVuZCgKICAgICAgICAiICAgIHN0YXR1cy51cGRhdGUoIgogICAgICAgICJfcHZuZXR3b3JrX2Rhc2hib2FyZF9uZXR3b3JrX3NuYXBzaG90KCkiCiAgICAgICAgIilcbiIKICAgICkKCmlmICgKICAgICJfcHZuZXR3b3JrX29wZW52cG5fb25saW5lX3NuYXBzaG90KCkiCiAgICBub3QgaW4gYmxvY2sKKToKICAgIGluc2VydGlvbnMuYXBwZW5kKAogICAgICAgICIgICAgc3RhdHVzLnVwZGF0ZSgiCiAgICAgICAgIl9wdm5ldHdvcmtfb3BlbnZwbl9vbmxpbmVfc25hcHNob3QoKSIKICAgICAgICAiKVxuIgogICAgKQoKCmlmIGluc2VydGlvbnM6CgogICAgcmV0dXJuX3BvcyA9IGJsb2NrLmZpbmQoCiAgICAgICAgIiAgICByZXR1cm4gUmVzcG9uc2VNb2RlbCgiCiAgICApCgogICAgaWYgcmV0dXJuX3BvcyA8IDA6CiAgICAgICAgcmFpc2UgU3lzdGVtRXhpdCgKICAgICAgICAgICAgIlNUQVRVU19SRVRVUk5fTk9UX0ZPVU5EIgogICAgICAgICkKCiAgICBibG9jayA9ICgKICAgICAgICBibG9ja1s6cmV0dXJuX3Bvc10KICAgICAgICArICIiLmpvaW4oaW5zZXJ0aW9ucykKICAgICAgICArIGJsb2NrW3JldHVybl9wb3M6XQogICAgKQoKICAgIHMgPSAoCiAgICAgICAgc1s6c3RhdHVzX3Bvc10KICAgICAgICArIGJsb2NrCiAgICAgICAgKyBzW3VzYWdlX3JvdXRlOl0KICAgICkKCgpyb3V0ZXJfZmlsZS53cml0ZV90ZXh0KAogICAgcywKICAgIGVuY29kaW5nPSJ1dGYtOCIsCikKCnByaW50KAogICAgIlBWTkVUV09SS19OT0RFX0NPTVBBVF9QQVRDSD1QQVNTIgopCg==' | base64 -d >/tmp/ov-node-compat-patch.py

python3 /tmp/ov-node-compat-patch.py "$NEW"

rm -f /tmp/ov-node-compat-patch.py

python3 -m py_compile \
  "$NEW/core/routers/router.py" \
  "$NEW/core/service/user_managment.py"

stage 58 compatibility "OV Node compatibility patch verified"

# PVNETWORK_USER_MANAGEMENT_COMPAT_V3
echo 'ZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCmltcG9ydCBzeXMKCnJvb3QgPSBQYXRoKHN5cy5hcmd2WzFdKQoKcCA9IHJvb3QgLyAiY29yZS9zZXJ2aWNlL3VzZXJfbWFuYWdtZW50LnB5IgoKaWYgbm90IHAuZXhpc3RzKCk6CiAgICByYWlzZSBTeXN0ZW1FeGl0KCJVU0VSX01BTkFHRU1FTlRfTk9UX0ZPVU5EIikKCnMgPSBwLnJlYWRfdGV4dCgKICAgIGVuY29kaW5nPSJ1dGYtOCIsCiAgICBlcnJvcnM9InJlcGxhY2UiLAopCgpmb3IgaW1wIGluICgKICAgICJpbXBvcnQgb3MiLAogICAgImltcG9ydCByZSIsCiAgICAiaW1wb3J0IHN1YnByb2Nlc3MiLAopOgogICAgaWYgaW1wIG5vdCBpbiBzOgogICAgICAgIHMgPSBpbXAgKyAiXG4iICsgcwoKCmRlZiByZXBsYWNlX2Z1bmN0aW9uKAogICAgdGV4dCwKICAgIGZ1bmN0aW9uX25hbWUsCiAgICBuZXh0X2Z1bmN0aW9uLAogICAgcmVwbGFjZW1lbnQsCik6CiAgICBzdGFydCA9IHRleHQuZmluZCgKICAgICAgICBmImRlZiB7ZnVuY3Rpb25fbmFtZX0iCiAgICApCgogICAgaWYgc3RhcnQgPCAwOgogICAgICAgIHJhaXNlIFJ1bnRpbWVFcnJvcigKICAgICAgICAgICAgZiJ7ZnVuY3Rpb25fbmFtZX1fTk9UX0ZPVU5EIgogICAgICAgICkKCiAgICBlbmQgPSB0ZXh0LmZpbmQoCiAgICAgICAgZiJcbmRlZiB7bmV4dF9mdW5jdGlvbn0iLAogICAgICAgIHN0YXJ0LAogICAgKQoKICAgIGlmIGVuZCA8IDA6CiAgICAgICAgcmFpc2UgUnVudGltZUVycm9yKAogICAgICAgICAgICBmIntuZXh0X2Z1bmN0aW9ufV9OT1RfRk9VTkQiCiAgICAgICAgKQoKICAgIHJldHVybiAoCiAgICAgICAgdGV4dFs6c3RhcnRdCiAgICAgICAgKyByZXBsYWNlbWVudAogICAgICAgICsgIlxuXG4iCiAgICAgICAgKyB0ZXh0W2VuZCArIDE6XQogICAgKQoKCmNyZWF0ZV9mdW5jID0gcicnJ2RlZiBjcmVhdGVfdXNlcl9vbl9zZXJ2ZXIobmFtZSkgLT4gYm9vbDoKICAgIHRyeToKICAgICAgICBuYW1lID0gc3RyKG5hbWUpLnN0cmlwKCkKCiAgICAgICAgaWYgbm90IHJlLmZ1bGxtYXRjaCgKICAgICAgICAgICAgciJbQS1aYS16MC05Xy1dezEsNjR9IiwKICAgICAgICAgICAgbmFtZSwKICAgICAgICApOgogICAgICAgICAgICBsb2dnZXIuZXJyb3IoCiAgICAgICAgICAgICAgICAiSW52YWxpZCBPcGVuVlBOIGNsaWVudCBuYW1lOiAlcyIsCiAgICAgICAgICAgICAgICBuYW1lLAogICAgICAgICAgICApCiAgICAgICAgICAgIHJldHVybiBGYWxzZQoKICAgICAgICBpbnN0YWxsZXIgPSAoCiAgICAgICAgICAgICIvcm9vdC9vcGVudnBuLWluc3RhbGwuc2giCiAgICAgICAgKQoKICAgICAgICBwcm9maWxlID0gKAogICAgICAgICAgICBmIi9yb290L3tuYW1lfS5vdnBuIgogICAgICAgICkKCiAgICAgICAgaWYgb3MucGF0aC5pc2RpcigKICAgICAgICAgICAgIi9ldGMvb3BlbnZwbi9zZXJ2ZXIvY2NkIgogICAgICAgICk6CiAgICAgICAgICAgIGNjZF9kaXIgPSAoCiAgICAgICAgICAgICAgICAiL2V0Yy9vcGVudnBuL3NlcnZlci9jY2QiCiAgICAgICAgICAgICkKICAgICAgICBlbHNlOgogICAgICAgICAgICBjY2RfZGlyID0gKAogICAgICAgICAgICAgICAgIi9ldGMvb3BlbnZwbi9jY2QiCiAgICAgICAgICAgICkKCiAgICAgICAgY2NkID0gKAogICAgICAgICAgICBmIntjY2RfZGlyfS97bmFtZX0iCiAgICAgICAgKQoKICAgICAgICBvcy5tYWtlZGlycygKICAgICAgICAgICAgY2NkX2RpciwKICAgICAgICAgICAgZXhpc3Rfb2s9VHJ1ZSwKICAgICAgICApCgogICAgICAgIGRlZiB2YWxpZF9wcm9maWxlKCk6CiAgICAgICAgICAgIGlmIG5vdCBvcy5wYXRoLmlzZmlsZSgKICAgICAgICAgICAgICAgIHByb2ZpbGUKICAgICAgICAgICAgKToKICAgICAgICAgICAgICAgIHJldHVybiBGYWxzZQoKICAgICAgICAgICAgaWYgb3MucGF0aC5nZXRzaXplKAogICAgICAgICAgICAgICAgcHJvZmlsZQogICAgICAgICAgICApIDwgNTAwOgogICAgICAgICAgICAgICAgcmV0dXJuIEZhbHNlCgogICAgICAgICAgICB0cnk6CiAgICAgICAgICAgICAgICB0ZXh0ID0gb3BlbigKICAgICAgICAgICAgICAgICAgICBwcm9maWxlLAogICAgICAgICAgICAgICAgICAgICJyIiwKICAgICAgICAgICAgICAgICAgICBlbmNvZGluZz0idXRmLTgiLAogICAgICAgICAgICAgICAgICAgIGVycm9ycz0iaWdub3JlIiwKICAgICAgICAgICAgICAgICkucmVhZCgpLmxvd2VyKCkKICAgICAgICAgICAgZXhjZXB0IE9TRXJyb3I6CiAgICAgICAgICAgICAgICByZXR1cm4gRmFsc2UKCiAgICAgICAgICAgIHJldHVybiBhbGwoCiAgICAgICAgICAgICAgICBtYXJrZXIgaW4gdGV4dAogICAgICAgICAgICAgICAgZm9yIG1hcmtlciBpbiAoCiAgICAgICAgICAgICAgICAgICAgIjxjYT4iLAogICAgICAgICAgICAgICAgICAgICI8L2NhPiIsCiAgICAgICAgICAgICAgICAgICAgIjxjZXJ0PiIsCiAgICAgICAgICAgICAgICAgICAgIjwvY2VydD4iLAogICAgICAgICAgICAgICAgICAgICI8a2V5PiIsCiAgICAgICAgICAgICAgICAgICAgIjwva2V5PiIsCiAgICAgICAgICAgICAgICAgICAgInJlbW90ZSAiLAogICAgICAgICAgICAgICAgKQogICAgICAgICAgICApCgogICAgICAgIGlmIHZhbGlkX3Byb2ZpbGUoKToKCiAgICAgICAgICAgIG9wZW4oCiAgICAgICAgICAgICAgICBjY2QsCiAgICAgICAgICAgICAgICAiYSIsCiAgICAgICAgICAgICkuY2xvc2UoKQoKICAgICAgICAgICAgb3MuY2htb2QoCiAgICAgICAgICAgICAgICBjY2QsCiAgICAgICAgICAgICAgICAwbzY0NCwKICAgICAgICAgICAgKQoKICAgICAgICAgICAgcmV0dXJuIFRydWUKCiAgICAgICAgaWYgbm90IG9zLnBhdGguaXNmaWxlKAogICAgICAgICAgICBpbnN0YWxsZXIKICAgICAgICApOgogICAgICAgICAgICBsb2dnZXIuZXJyb3IoCiAgICAgICAgICAgICAgICAiT3BlblZQTiBpbnN0YWxsZXIgbWlzc2luZyIKICAgICAgICAgICAgKQogICAgICAgICAgICByZXR1cm4gRmFsc2UKCiAgICAgICAgdHJ5OgogICAgICAgICAgICBpZiBvcy5wYXRoLmV4aXN0cygKICAgICAgICAgICAgICAgIHByb2ZpbGUKICAgICAgICAgICAgKToKICAgICAgICAgICAgICAgIG9zLnJlbW92ZSgKICAgICAgICAgICAgICAgICAgICBwcm9maWxlCiAgICAgICAgICAgICAgICApCiAgICAgICAgZXhjZXB0IE9TRXJyb3I6CiAgICAgICAgICAgIHBhc3MKCiAgICAgICAgZW52ID0gb3MuZW52aXJvbi5jb3B5KCkKCiAgICAgICAgZW52WyJQQVRIIl0gPSAoCiAgICAgICAgICAgICIvdXNyL2xvY2FsL3NiaW46IgogICAgICAgICAgICAiL3Vzci9sb2NhbC9iaW46IgogICAgICAgICAgICAiL3Vzci9zYmluOiIKICAgICAgICAgICAgIi91c3IvYmluOiIKICAgICAgICAgICAgIi9zYmluOiIKICAgICAgICAgICAgIi9iaW4iCiAgICAgICAgKQoKICAgICAgICBkZWYgYWRkX2NsaWVudCgpOgogICAgICAgICAgICByZXR1cm4gc3VicHJvY2Vzcy5ydW4oCiAgICAgICAgICAgICAgICBbCiAgICAgICAgICAgICAgICAgICAgaW5zdGFsbGVyLAogICAgICAgICAgICAgICAgICAgICJjbGllbnQiLAogICAgICAgICAgICAgICAgICAgICJhZGQiLAogICAgICAgICAgICAgICAgICAgIG5hbWUsCiAgICAgICAgICAgICAgICAgICAgIi0tb3V0cHV0IiwKICAgICAgICAgICAgICAgICAgICBwcm9maWxlLAogICAgICAgICAgICAgICAgXSwKICAgICAgICAgICAgICAgIGVudj1lbnYsCiAgICAgICAgICAgICAgICBzdGRvdXQ9c3VicHJvY2Vzcy5QSVBFLAogICAgICAgICAgICAgICAgc3RkZXJyPXN1YnByb2Nlc3MuU1RET1VULAogICAgICAgICAgICAgICAgdGV4dD1UcnVlLAogICAgICAgICAgICAgICAgdGltZW91dD0xODAsCiAgICAgICAgICAgICAgICBjaGVjaz1GYWxzZSwKICAgICAgICAgICAgKQoKICAgICAgICByZXN1bHQgPSBhZGRfY2xpZW50KCkKCiAgICAgICAgaWYgKAogICAgICAgICAgICByZXN1bHQucmV0dXJuY29kZSAhPSAwCiAgICAgICAgICAgIG9yIG5vdCB2YWxpZF9wcm9maWxlKCkKICAgICAgICApOgogICAgICAgICAgICBsb2dnZXIud2FybmluZygKICAgICAgICAgICAgICAgICJJbml0aWFsIGNsaWVudCBjcmVhdGlvbiAiCiAgICAgICAgICAgICAgICAiZmFpbGVkIGZvciAlczogJXMiLAogICAgICAgICAgICAgICAgbmFtZSwKICAgICAgICAgICAgICAgIChyZXN1bHQuc3Rkb3V0IG9yICIiKVsKICAgICAgICAgICAgICAgICAgICAtMTIwMDoKICAgICAgICAgICAgICAgIF0sCiAgICAgICAgICAgICkKCiAgICAgICAgICAgICMgU3RhbGUgUEtJIGVudHJ5IGZyb20gYW4gb2xkZXIKICAgICAgICAgICAgIyBmYWlsZWQgcHJvdmlzaW9uaW5nIGF0dGVtcHQuCiAgICAgICAgICAgIHN1YnByb2Nlc3MucnVuKAogICAgICAgICAgICAgICAgWwogICAgICAgICAgICAgICAgICAgIGluc3RhbGxlciwKICAgICAgICAgICAgICAgICAgICAiY2xpZW50IiwKICAgICAgICAgICAgICAgICAgICAicmV2b2tlIiwKICAgICAgICAgICAgICAgICAgICBuYW1lLAogICAgICAgICAgICAgICAgICAgICItLWZvcmNlIiwKICAgICAgICAgICAgICAgIF0sCiAgICAgICAgICAgICAgICBlbnY9ZW52LAogICAgICAgICAgICAgICAgc3Rkb3V0PXN1YnByb2Nlc3MuUElQRSwKICAgICAgICAgICAgICAgIHN0ZGVycj1zdWJwcm9jZXNzLlNURE9VVCwKICAgICAgICAgICAgICAgIHRleHQ9VHJ1ZSwKICAgICAgICAgICAgICAgIHRpbWVvdXQ9MTgwLAogICAgICAgICAgICAgICAgY2hlY2s9RmFsc2UsCiAgICAgICAgICAgICkKCiAgICAgICAgICAgIHRyeToKICAgICAgICAgICAgICAgIGlmIG9zLnBhdGguZXhpc3RzKAogICAgICAgICAgICAgICAgICAgIHByb2ZpbGUKICAgICAgICAgICAgICAgICk6CiAgICAgICAgICAgICAgICAgICAgb3MucmVtb3ZlKAogICAgICAgICAgICAgICAgICAgICAgICBwcm9maWxlCiAgICAgICAgICAgICAgICAgICAgKQogICAgICAgICAgICBleGNlcHQgT1NFcnJvcjoKICAgICAgICAgICAgICAgIHBhc3MKCiAgICAgICAgICAgIHJlc3VsdCA9IGFkZF9jbGllbnQoKQoKICAgICAgICBpZiBub3QgdmFsaWRfcHJvZmlsZSgpOgoKICAgICAgICAgICAgbG9nZ2VyLmVycm9yKAogICAgICAgICAgICAgICAgIkNvdWxkIG5vdCBjcmVhdGUgdmFsaWQgIgogICAgICAgICAgICAgICAgIk9WUE4gcHJvZmlsZSBmb3IgJXM6ICVzIiwKICAgICAgICAgICAgICAgIG5hbWUsCiAgICAgICAgICAgICAgICAocmVzdWx0LnN0ZG91dCBvciAiIilbCiAgICAgICAgICAgICAgICAgICAgLTE4MDA6CiAgICAgICAgICAgICAgICBdLAogICAgICAgICAgICApCgogICAgICAgICAgICByZXR1cm4gRmFsc2UKCiAgICAgICAgb3BlbigKICAgICAgICAgICAgY2NkLAogICAgICAgICAgICAiYSIsCiAgICAgICAgKS5jbG9zZSgpCgogICAgICAgIG9zLmNobW9kKAogICAgICAgICAgICBjY2QsCiAgICAgICAgICAgIDBvNjQ0LAogICAgICAgICkKCiAgICAgICAgbG9nZ2VyLmluZm8oCiAgICAgICAgICAgICJPcGVuVlBOIHByb2ZpbGUgcmVhZHk6ICVzIiwKICAgICAgICAgICAgbmFtZSwKICAgICAgICApCgogICAgICAgIHJldHVybiBUcnVlCgogICAgZXhjZXB0IHN1YnByb2Nlc3MuVGltZW91dEV4cGlyZWQ6CiAgICAgICAgbG9nZ2VyLmVycm9yKAogICAgICAgICAgICAiVGltZW91dCBjcmVhdGluZyB1c2VyOiAlcyIsCiAgICAgICAgICAgIG5hbWUsCiAgICAgICAgKQoKICAgICAgICByZXR1cm4gRmFsc2UKCiAgICBleGNlcHQgRXhjZXB0aW9uIGFzIGV4YzoKICAgICAgICBsb2dnZXIuZXhjZXB0aW9uKAogICAgICAgICAgICAiVXNlciBjcmVhdGlvbiBmYWlsZWQgJXM6ICVzIiwKICAgICAgICAgICAgbmFtZSwKICAgICAgICAgICAgZXhjLAogICAgICAgICkKCiAgICAgICAgcmV0dXJuIEZhbHNlJycnCgoKZGVsZXRlX2Z1bmMgPSByJycnZGVmIGRlbGV0ZV91c2VyX29uX3NlcnZlcihuYW1lKSAtPiBib29sIHwgc3RyOgogICAgdHJ5OgogICAgICAgIG5hbWUgPSBzdHIobmFtZSkuc3RyaXAoKQoKICAgICAgICBpZiBub3QgcmUuZnVsbG1hdGNoKAogICAgICAgICAgICByIltBLVphLXowLTlfLV17MSw2NH0iLAogICAgICAgICAgICBuYW1lLAogICAgICAgICk6CiAgICAgICAgICAgIHJldHVybiBGYWxzZQoKICAgICAgICBpbnN0YWxsZXIgPSAoCiAgICAgICAgICAgICIvcm9vdC9vcGVudnBuLWluc3RhbGwuc2giCiAgICAgICAgKQoKICAgICAgICByZXN1bHQgPSBOb25lCgogICAgICAgIGlmIG9zLnBhdGguaXNmaWxlKAogICAgICAgICAgICBpbnN0YWxsZXIKICAgICAgICApOgogICAgICAgICAgICByZXN1bHQgPSBzdWJwcm9jZXNzLnJ1bigKICAgICAgICAgICAgICAgIFsKICAgICAgICAgICAgICAgICAgICBpbnN0YWxsZXIsCiAgICAgICAgICAgICAgICAgICAgImNsaWVudCIsCiAgICAgICAgICAgICAgICAgICAgInJldm9rZSIsCiAgICAgICAgICAgICAgICAgICAgbmFtZSwKICAgICAgICAgICAgICAgICAgICAiLS1mb3JjZSIsCiAgICAgICAgICAgICAgICBdLAogICAgICAgICAgICAgICAgc3Rkb3V0PXN1YnByb2Nlc3MuUElQRSwKICAgICAgICAgICAgICAgIHN0ZGVycj1zdWJwcm9jZXNzLlNURE9VVCwKICAgICAgICAgICAgICAgIHRleHQ9VHJ1ZSwKICAgICAgICAgICAgICAgIHRpbWVvdXQ9MTgwLAogICAgICAgICAgICAgICAgY2hlY2s9RmFsc2UsCiAgICAgICAgICAgICkKCiAgICAgICAgZm9yIHBhdGggaW4gKAogICAgICAgICAgICBmIi9yb290L3tuYW1lfS5vdnBuIiwKICAgICAgICAgICAgZiIvZXRjL29wZW52cG4vY2NkL3tuYW1lfSIsCiAgICAgICAgICAgIGYiL2V0Yy9vcGVudnBuL3NlcnZlci9jY2Qve25hbWV9IiwKICAgICAgICApOgogICAgICAgICAgICB0cnk6CiAgICAgICAgICAgICAgICBpZiBvcy5wYXRoLmV4aXN0cyhwYXRoKToKICAgICAgICAgICAgICAgICAgICBvcy5yZW1vdmUocGF0aCkKICAgICAgICAgICAgZXhjZXB0IE9TRXJyb3I6CiAgICAgICAgICAgICAgICBwYXNzCgogICAgICAgIGlmIHJlc3VsdCBpcyBOb25lOgogICAgICAgICAgICByZXR1cm4gRmFsc2UKCiAgICAgICAgaWYgcmVzdWx0LnJldHVybmNvZGUgPT0gMDoKICAgICAgICAgICAgcmV0dXJuIFRydWUKCiAgICAgICAgb3V0cHV0ID0gKAogICAgICAgICAgICByZXN1bHQuc3Rkb3V0IG9yICIiCiAgICAgICAgKS5sb3dlcigpCgogICAgICAgIGlmIGFueSgKICAgICAgICAgICAgeCBpbiBvdXRwdXQKICAgICAgICAgICAgZm9yIHggaW4gKAogICAgICAgICAgICAgICAgIm5vdCBmb3VuZCIsCiAgICAgICAgICAgICAgICAiZG9lcyBub3QgZXhpc3QiLAogICAgICAgICAgICAgICAgImFscmVhZHkgcmV2b2tlZCIsCiAgICAgICAgICAgICkKICAgICAgICApOgogICAgICAgICAgICByZXR1cm4gIm5vdF9mb3VuZCIKCiAgICAgICAgcmV0dXJuIEZhbHNlCgogICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBleGM6CiAgICAgICAgbG9nZ2VyLmV4Y2VwdGlvbigKICAgICAgICAgICAgIkRlbGV0ZSBmYWlsZWQgJXM6ICVzIiwKICAgICAgICAgICAgbmFtZSwKICAgICAgICAgICAgZXhjLAogICAgICAgICkKCiAgICAgICAgcmV0dXJuIEZhbHNlJycnCgoKY2hhbmdlX2Z1bmMgPSByJycnZGVmIGNoYW5nZV91c2VyX3N0YXR1cyhuYW1lOiBzdHIsIHN0YXR1czogc3RyKSAtPiBib29sOgogICAgdHJ5OgogICAgICAgIGlmIG9zLnBhdGguaXNkaXIoCiAgICAgICAgICAgICIvZXRjL29wZW52cG4vc2VydmVyL2NjZCIKICAgICAgICApOgogICAgICAgICAgICBjY2RfZGlyID0gKAogICAgICAgICAgICAgICAgIi9ldGMvb3BlbnZwbi9zZXJ2ZXIvY2NkIgogICAgICAgICAgICApCiAgICAgICAgZWxzZToKICAgICAgICAgICAgY2NkX2RpciA9ICgKICAgICAgICAgICAgICAgICIvZXRjL29wZW52cG4vY2NkIgogICAgICAgICAgICApCgogICAgICAgIG9zLm1ha2VkaXJzKAogICAgICAgICAgICBjY2RfZGlyLAogICAgICAgICAgICBleGlzdF9vaz1UcnVlLAogICAgICAgICkKCiAgICAgICAgY2NkID0gKAogICAgICAgICAgICBmIntjY2RfZGlyfS97bmFtZX0iCiAgICAgICAgKQoKICAgICAgICBpZiBzdGF0dXMgPT0gImRlYWN0aXZhdGUiOgoKICAgICAgICAgICAgaWYgb3MucGF0aC5leGlzdHMoCiAgICAgICAgICAgICAgICBjY2QKICAgICAgICAgICAgKToKICAgICAgICAgICAgICAgIG9zLnJlbW92ZSgKICAgICAgICAgICAgICAgICAgICBjY2QKICAgICAgICAgICAgICAgICkKCiAgICAgICAgICAgIHJldHVybiBUcnVlCgogICAgICAgIGlmIHN0YXR1cyA9PSAiYWN0aXZhdGUiOgoKICAgICAgICAgICAgb3BlbigKICAgICAgICAgICAgICAgIGNjZCwKICAgICAgICAgICAgICAgICJhIiwKICAgICAgICAgICAgKS5jbG9zZSgpCgogICAgICAgICAgICBvcy5jaG1vZCgKICAgICAgICAgICAgICAgIGNjZCwKICAgICAgICAgICAgICAgIDBvNjQ0LAogICAgICAgICAgICApCgogICAgICAgICAgICByZXR1cm4gVHJ1ZQoKICAgICAgICByZXR1cm4gRmFsc2UKCiAgICBleGNlcHQgRXhjZXB0aW9uIGFzIGV4YzoKCiAgICAgICAgbG9nZ2VyLmVycm9yKAogICAgICAgICAgICAiU3RhdHVzIGNoYW5nZSBmYWlsZWQgJXM6ICVzIiwKICAgICAgICAgICAgbmFtZSwKICAgICAgICAgICAgZXhjLAogICAgICAgICkKCiAgICAgICAgcmV0dXJuIEZhbHNlJycnCgoKcyA9IHJlcGxhY2VfZnVuY3Rpb24oCiAgICBzLAogICAgImNyZWF0ZV91c2VyX29uX3NlcnZlciIsCiAgICAiZGVsZXRlX3VzZXJfb25fc2VydmVyIiwKICAgIGNyZWF0ZV9mdW5jLAopCgpzID0gcmVwbGFjZV9mdW5jdGlvbigKICAgIHMsCiAgICAiZGVsZXRlX3VzZXJfb25fc2VydmVyIiwKICAgICJjaGFuZ2VfdXNlcl9zdGF0dXMiLAogICAgZGVsZXRlX2Z1bmMsCikKCnMgPSByZXBsYWNlX2Z1bmN0aW9uKAogICAgcywKICAgICJjaGFuZ2VfdXNlcl9zdGF0dXMiLAogICAgInJlc3RhcnRfb3BlbnZwbl9zZXJ2aWNlIiwKICAgIGNoYW5nZV9mdW5jLAopCgpwLndyaXRlX3RleHQoCiAgICBzLAogICAgZW5jb2Rpbmc9InV0Zi04IiwKKQoKcHJpbnQoCiAgICAiVVNFUl9NQU5BR0VNRU5UX1YzPVBBU1MiCikK' | base64 -d >/tmp/ov-user-create-v3.py
python3 /tmp/ov-user-create-v3.py "$NEW"
rm -f /tmp/ov-user-create-v3.py
python3 -m py_compile "$NEW/core/service/user_managment.py"
stage 59 user_engine "OV Node user engine verified"



# PVNETWORK_PROFILE_BUILDER_V1
stage 60 profile_builder "Installing PVNetwork profile builder"
install -d -m 0755 /usr/local/sbin
echo 'IyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLUVldW8gcGlwZWZhaWwKCk5BTUU9IiR7MTotfSIKCmlmICEgW1sgIiROQU1FIiA9fiBeW0EtWmEtejAtOV8tXSskIF1dOyB0aGVuCiAgICBlY2hvICJJTlZBTElEX05BTUU9JE5BTUUiID4mMgogICAgZXhpdCAyCmZpCgppZiAoKCAkeyNOQU1FfSA+IDY0ICkpOyB0aGVuCiAgICBlY2hvICJOQU1FX1RPT19MT05HPSROQU1FIiA+JjIKICAgIGV4aXQgMgpmaQoKQkFTRT0iL2V0Yy9vcGVudnBuL3NlcnZlciIKRUFTWT0iJEJBU0UvZWFzeS1yc2EiClBLST0iJEVBU1kvcGtpIgoKU0VSVkVSPSIkQkFTRS9zZXJ2ZXIuY29uZiIKVEVNUExBVEU9IiRCQVNFL2NsaWVudC10ZW1wbGF0ZS50eHQiCgpQUk9GSUxFPSIvcm9vdC8ke05BTUV9Lm92cG4iCgpDRVJUPSIkUEtJL2lzc3VlZC8ke05BTUV9LmNydCIKS0VZPSIkUEtJL3ByaXZhdGUvJHtOQU1FfS5rZXkiClJFUT0iJFBLSS9yZXFzLyR7TkFNRX0ucmVxIgoKSU5ERVg9IiRQS0kvaW5kZXgudHh0IgoKVE1QX1BST0ZJTEU9IiIKVExTX1RNUD0iIgoKY2xlYW51cCgpIHsKICAgIFtbIC16ICIkVE1QX1BST0ZJTEUiIF1dIFwKICAgICAgICB8fCBybSAtZiAiJFRNUF9QUk9GSUxFIgoKICAgIFtbIC16ICIkVExTX1RNUCIgXV0gXAogICAgICAgIHx8IHJtIC1mICIkVExTX1RNUCIKfQoKdHJhcCBjbGVhbnVwIEVYSVQKCgp2YWxpZF9wcm9maWxlKCkgewoKICAgIFtbIC1zICIkUFJPRklMRSIgXV0gfHwgcmV0dXJuIDEKCiAgICBbWyAiJChzdGF0IC1jICVzICIkUFJPRklMRSIpIiAtZ3QgNTAwIF1dIFwKICAgICAgICB8fCByZXR1cm4gMQoKICAgIGdyZXAgLXFpICc8Y2E+JyAiJFBST0ZJTEUiIHx8IHJldHVybiAxCiAgICBncmVwIC1xaSAnPC9jYT4nICIkUFJPRklMRSIgfHwgcmV0dXJuIDEKCiAgICBncmVwIC1xaSAnPGNlcnQ+JyAiJFBST0ZJTEUiIHx8IHJldHVybiAxCiAgICBncmVwIC1xaSAnPC9jZXJ0PicgIiRQUk9GSUxFIiB8fCByZXR1cm4gMQoKICAgIGdyZXAgLXFpICc8a2V5PicgIiRQUk9GSUxFIiB8fCByZXR1cm4gMQogICAgZ3JlcCAtcWkgJzwva2V5PicgIiRQUk9GSUxFIiB8fCByZXR1cm4gMQoKICAgIGdyZXAgLXFpICdecmVtb3RlICcgIiRQUk9GSUxFIiB8fCByZXR1cm4gMQoKICAgIHJldHVybiAwCn0KCgp2YWxpZF9wa2lfZW50cnkoKSB7CgogICAgW1sgLXMgIiRJTkRFWCIgXV0gfHwgcmV0dXJuIDEKCiAgICBhd2sgXAogICAgICAgIC1GICdcdCcgXAogICAgICAgIC12IG49IiROQU1FIiBcCiAgICAgICAgJwogICAgICAgICQxID09ICJWIiAmJiAkTkYgPT0gIi9DTj0iIG4gewogICAgICAgICAgICBmb3VuZD0xCiAgICAgICAgfQoKICAgICAgICBFTkQgewogICAgICAgICAgICBleGl0KGZvdW5kID8gMCA6IDEpCiAgICAgICAgfQogICAgICAgICcgXAogICAgICAgICIkSU5ERVgiCn0KCgpyZXNvbHZlX3NlcnZlcl9maWxlKCkgewoKICAgIGxvY2FsIHZhbHVlPSIkMSIKCiAgICBpZiBbWyAiJHZhbHVlIiA9PSAvKiBdXTsgdGhlbgogICAgICAgIHByaW50ZiAnJXNcbicgIiR2YWx1ZSIKICAgIGVsc2UKICAgICAgICBwcmludGYgJyVzLyVzXG4nICIkQkFTRSIgIiR2YWx1ZSIKICAgIGZpCn0KCgpidWlsZF9wcm9maWxlKCkgewoKICAgIFtbIC1zICIkVEVNUExBVEUiIF1dIHx8IHsKICAgICAgICBlY2hvICJDTElFTlRfVEVNUExBVEVfTUlTU0lORyIgPiYyCiAgICAgICAgcmV0dXJuIDEKICAgIH0KCiAgICBbWyAtcyAiJFBLSS9jYS5jcnQiIF1dIHx8IHsKICAgICAgICBlY2hvICJDQV9NSVNTSU5HIiA+JjIKICAgICAgICByZXR1cm4gMQogICAgfQoKICAgIFtbIC1zICIkQ0VSVCIgXV0gfHwgewogICAgICAgIGVjaG8gIkNFUlRfTUlTU0lORz0kQ0VSVCIgPiYyCiAgICAgICAgcmV0dXJuIDEKICAgIH0KCiAgICBbWyAtcyAiJEtFWSIgXV0gfHwgewogICAgICAgIGVjaG8gIktFWV9NSVNTSU5HPSRLRVkiID4mMgogICAgICAgIHJldHVybiAxCiAgICB9CgogICAgVE1QX1BST0ZJTEU9IiQoCiAgICAgICAgbWt0ZW1wIFwKICAgICAgICAiL3Jvb3QvLiR7TkFNRX0ub3Zwbi5YWFhYWFgiCiAgICApIgoKICAgIGNhdCAiJFRFTVBMQVRFIiBcCiAgICAgICAgPiIkVE1QX1BST0ZJTEUiCgogICAgewogICAgICAgIGVjaG8KICAgICAgICBlY2hvICI8Y2E+IgogICAgICAgIGNhdCAiJFBLSS9jYS5jcnQiCiAgICAgICAgZWNobyAiPC9jYT4iCgogICAgICAgIGVjaG8gIjxjZXJ0PiIKCiAgICAgICAgYXdrIFwKICAgICAgICAgICAgJy8tLS0tLUJFR0lOIENFUlRJRklDQVRFLS0tLS0vLC8tLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tLycgXAogICAgICAgICAgICAiJENFUlQiCgogICAgICAgIGVjaG8gIjwvY2VydD4iCgogICAgICAgIGVjaG8gIjxrZXk+IgogICAgICAgIGNhdCAiJEtFWSIKICAgICAgICBlY2hvICI8L2tleT4iCiAgICB9ID4+IiRUTVBfUFJPRklMRSIKCgogICAgaWYgZ3JlcCAtcXMgXAogICAgICAgICdedGxzLWNyeXB0LXYyW1s6c3BhY2U6XV0nIFwKICAgICAgICAiJFNFUlZFUiIKICAgIHRoZW4KCiAgICAgICAgVExTX1NFUlZFUl9LRVk9IiQoCiAgICAgICAgICAgIGF3ayBcCiAgICAgICAgICAgICAgICAnJDE9PSJ0bHMtY3J5cHQtdjIie3ByaW50ICQyOyBleGl0fScgXAogICAgICAgICAgICAgICAgIiRTRVJWRVIiCiAgICAgICAgKSIKCiAgICAgICAgVExTX1NFUlZFUl9LRVk9IiQoCiAgICAgICAgICAgIHJlc29sdmVfc2VydmVyX2ZpbGUgXAogICAgICAgICAgICAiJFRMU19TRVJWRVJfS0VZIgogICAgICAgICkiCgogICAgICAgIHRlc3QgLXMgIiRUTFNfU0VSVkVSX0tFWSIKCiAgICAgICAgVExTX1RNUD0iJCgKICAgICAgICAgICAgbWt0ZW1wIFwKICAgICAgICAgICAgIiRCQVNFL3Rscy1jcnlwdC12Mi1jbGllbnQuWFhYWFhYIgogICAgICAgICkiCgogICAgICAgIG9wZW52cG4gXAogICAgICAgICAgICAtLXRscy1jcnlwdC12MiAiJFRMU19TRVJWRVJfS0VZIiBcCiAgICAgICAgICAgIC0tZ2Vua2V5IHRscy1jcnlwdC12Mi1jbGllbnQgIiRUTFNfVE1QIgoKICAgICAgICB7CiAgICAgICAgICAgIGVjaG8gIjx0bHMtY3J5cHQtdjI+IgogICAgICAgICAgICBjYXQgIiRUTFNfVE1QIgogICAgICAgICAgICBlY2hvICI8L3Rscy1jcnlwdC12Mj4iCiAgICAgICAgfSA+PiIkVE1QX1BST0ZJTEUiCgogICAgICAgIHJtIC1mICIkVExTX1RNUCIKICAgICAgICBUTFNfVE1QPSIiCgoKICAgIGVsaWYgZ3JlcCAtcXMgXAogICAgICAgICdedGxzLWNyeXB0W1s6c3BhY2U6XV0nIFwKICAgICAgICAiJFNFUlZFUiIKICAgIHRoZW4KCiAgICAgICAgVExTX0tFWT0iJCgKICAgICAgICAgICAgYXdrIFwKICAgICAgICAgICAgICAgICckMT09InRscy1jcnlwdCJ7cHJpbnQgJDI7IGV4aXR9JyBcCiAgICAgICAgICAgICAgICAiJFNFUlZFUiIKICAgICAgICApIgoKICAgICAgICBUTFNfS0VZPSIkKAogICAgICAgICAgICByZXNvbHZlX3NlcnZlcl9maWxlIFwKICAgICAgICAgICAgIiRUTFNfS0VZIgogICAgICAgICkiCgogICAgICAgIHRlc3QgLXMgIiRUTFNfS0VZIgoKICAgICAgICB7CiAgICAgICAgICAgIGVjaG8gIjx0bHMtY3J5cHQ+IgogICAgICAgICAgICBjYXQgIiRUTFNfS0VZIgogICAgICAgICAgICBlY2hvICI8L3Rscy1jcnlwdD4iCiAgICAgICAgfSA+PiIkVE1QX1BST0ZJTEUiCgoKICAgIGVsaWYgZ3JlcCAtcXMgXAogICAgICAgICdedGxzLWF1dGhbWzpzcGFjZTpdXScgXAogICAgICAgICIkU0VSVkVSIgogICAgdGhlbgoKICAgICAgICBUTFNfS0VZPSIkKAogICAgICAgICAgICBhd2sgXAogICAgICAgICAgICAgICAgJyQxPT0idGxzLWF1dGgie3ByaW50ICQyOyBleGl0fScgXAogICAgICAgICAgICAgICAgIiRTRVJWRVIiCiAgICAgICAgKSIKCiAgICAgICAgVExTX0tFWT0iJCgKICAgICAgICAgICAgcmVzb2x2ZV9zZXJ2ZXJfZmlsZSBcCiAgICAgICAgICAgICIkVExTX0tFWSIKICAgICAgICApIgoKICAgICAgICB0ZXN0IC1zICIkVExTX0tFWSIKCiAgICAgICAgewogICAgICAgICAgICBlY2hvICJrZXktZGlyZWN0aW9uIDEiCiAgICAgICAgICAgIGVjaG8gIjx0bHMtYXV0aD4iCiAgICAgICAgICAgIGNhdCAiJFRMU19LRVkiCiAgICAgICAgICAgIGVjaG8gIjwvdGxzLWF1dGg+IgogICAgICAgIH0gPj4iJFRNUF9QUk9GSUxFIgogICAgZmkKCgogICAgY2htb2QgNjAwIFwKICAgICAgICAiJFRNUF9QUk9GSUxFIgoKICAgIG12IC1mIFwKICAgICAgICAiJFRNUF9QUk9GSUxFIiBcCiAgICAgICAgIiRQUk9GSUxFIgoKICAgIFRNUF9QUk9GSUxFPSIiCgogICAgbWtkaXIgLXAgXAogICAgICAgICIkQkFTRS9jY2QiCgogICAgdG91Y2ggXAogICAgICAgICIkQkFTRS9jY2QvJE5BTUUiCgogICAgY2htb2QgNjQ0IFwKICAgICAgICAiJEJBU0UvY2NkLyROQU1FIgoKICAgIG1rZGlyIC1wIFwKICAgICAgICAvZXRjL29wZW52cG4vY2NkCgogICAgdG91Y2ggXAogICAgICAgICIvZXRjL29wZW52cG4vY2NkLyROQU1FIgoKICAgIGNobW9kIDY0NCBcCiAgICAgICAgIi9ldGMvb3BlbnZwbi9jY2QvJE5BTUUiCgogICAgdmFsaWRfcHJvZmlsZQp9CgoKIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KIyBFeGlzdGluZyB2YWxpZCBPVlBOID0+IG5vdGhpbmcgdG8gZG8KIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KCmlmIHZhbGlkX3Byb2ZpbGU7IHRoZW4KICAgIGV4aXQgMApmaQoKCiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCiMgVmFsaWQgY2VydGlmaWNhdGUgYWxyZWFkeSBleGlzdHMuCiMgSnVzdCByZWJ1aWxkIHRoZSBtaXNzaW5nIE9WUE4gcHJvZmlsZS4KIyBObyBjZXJ0aWZpY2F0ZSByb3RhdGlvbi4KIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KCmlmIFwKICAgIHZhbGlkX3BraV9lbnRyeSBcCiAgICAmJiBbWyAtcyAiJENFUlQiIF1dIFwKICAgICYmIFtbIC1zICIkS0VZIiBdXQp0aGVuCgogICAgYnVpbGRfcHJvZmlsZQoKICAgIGVjaG8gIlBST0ZJTEVfUkVCVUlMVF9GUk9NX0VYSVNUSU5HX1BLST0kTkFNRSIKICAgIGV4aXQgMApmaQoKCiMgLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tCiMgTm8gVkFMSUQgUEtJIGVudHJ5LgojIE9sZCBmaWxlcyBhcmUgc3RhbGUgbGVmdG92ZXJzIGFuZCBtYXkgYmxvY2sgRWFzeVJTQS4KIyBSZW1vdmUgb25seSBmaWxlcyBiZWxvbmdpbmcgdG8gdGhpcyBub24tdmFsaWQgQ04sCiMgdGhlbiBnZW5lcmF0ZSBhIGZyZXNoIGNsaWVudCBjZXJ0aWZpY2F0ZS4KIyAtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0KCmlmIHZhbGlkX3BraV9lbnRyeTsgdGhlbgoKICAgIGVjaG8gXAogICAgICAiVkFMSURfSU5ERVhfQlVUX0NFUlRfT1JfS0VZX01JU1NJTkc9JE5BTUUiIFwKICAgICAgPiYyCgogICAgZXhpdCAxMgpmaQoKCnJtIC1mIFwKICAgICIkQ0VSVCIgXAogICAgIiRLRVkiIFwKICAgICIkUkVRIgoKY2QgIiRFQVNZIgoKZXhwb3J0IEVBU1lSU0FfQ0VSVF9FWFBJUkU9MzY1MAoKLi9lYXN5cnNhIFwKICAgIC0tYmF0Y2ggXAogICAgYnVpbGQtY2xpZW50LWZ1bGwgXAogICAgIiROQU1FIiBcCiAgICBub3Bhc3MKCmJ1aWxkX3Byb2ZpbGUKCmVjaG8gIlBST0ZJTEVfQ1JFQVRFRF9XSVRIX0ZSRVNIX1BLST0kTkFNRSIKZXhpdCAwCg==' | base64 -d >/usr/local/sbin/pvnetwork-build-client-profile
chmod 0755 /usr/local/sbin/pvnetwork-build-client-profile
echo 'ZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCmltcG9ydCBhc3QKaW1wb3J0IHN5cwoKcm9vdCA9IFBhdGgoc3lzLmFyZ3ZbMV0pCgpwID0gKAogICAgcm9vdAogICAgLyAiY29yZS9zZXJ2aWNlL3VzZXJfbWFuYWdtZW50LnB5IgopCgpzb3VyY2UgPSBwLnJlYWRfdGV4dCgKICAgIGVuY29kaW5nPSJ1dGYtOCIsCiAgICBlcnJvcnM9InJlcGxhY2UiLAopCgp0cmVlID0gYXN0LnBhcnNlKHNvdXJjZSkKCnRhcmdldCA9IE5vbmUKCmZvciBpdGVtIGluIHRyZWUuYm9keToKCiAgICBpZiAoCiAgICAgICAgaXNpbnN0YW5jZSgKICAgICAgICAgICAgaXRlbSwKICAgICAgICAgICAgKAogICAgICAgICAgICAgICAgYXN0LkZ1bmN0aW9uRGVmLAogICAgICAgICAgICAgICAgYXN0LkFzeW5jRnVuY3Rpb25EZWYsCiAgICAgICAgICAgICksCiAgICAgICAgKQogICAgICAgIGFuZCBpdGVtLm5hbWUKICAgICAgICA9PSAiY3JlYXRlX3VzZXJfb25fc2VydmVyIgogICAgKToKICAgICAgICB0YXJnZXQgPSBpdGVtCiAgICAgICAgYnJlYWsKCmlmIHRhcmdldCBpcyBOb25lOgogICAgcmFpc2UgU3lzdGVtRXhpdCgKICAgICAgICAiQ1JFQVRFX1VTRVJfRlVOQ1RJT05fTk9UX0ZPVU5EIgogICAgKQoKCnJlcGxhY2VtZW50ID0gJycnZGVmIGNyZWF0ZV91c2VyX29uX3NlcnZlcihuYW1lKSAtPiBib29sOgogICAgaW1wb3J0IG9zIGFzIF9vcwogICAgaW1wb3J0IHJlIGFzIF9yZQogICAgaW1wb3J0IHN1YnByb2Nlc3MgYXMgX3N1YnByb2Nlc3MKCiAgICB0cnk6CiAgICAgICAgbmFtZSA9IHN0cihuYW1lKS5zdHJpcCgpCgogICAgICAgIGlmIG5vdCBfcmUuZnVsbG1hdGNoKAogICAgICAgICAgICByIltBLVphLXowLTlfLV17MSw2NH0iLAogICAgICAgICAgICBuYW1lLAogICAgICAgICk6CiAgICAgICAgICAgIGxvZ2dlci5lcnJvcigKICAgICAgICAgICAgICAgICJJbnZhbGlkIE9wZW5WUE4gY2xpZW50IG5hbWU6ICVzIiwKICAgICAgICAgICAgICAgIG5hbWUsCiAgICAgICAgICAgICkKICAgICAgICAgICAgcmV0dXJuIEZhbHNlCgogICAgICAgIGhlbHBlciA9ICgKICAgICAgICAgICAgIi91c3IvbG9jYWwvc2Jpbi8iCiAgICAgICAgICAgICJvdi1idWlsZC1jbGllbnQtcHJvZmlsZSIKICAgICAgICApCgogICAgICAgIGlmIG5vdCBfb3MucGF0aC5pc2ZpbGUoaGVscGVyKToKICAgICAgICAgICAgbG9nZ2VyLmVycm9yKAogICAgICAgICAgICAgICAgIlByb2ZpbGUgYnVpbGRlciBtaXNzaW5nOiAlcyIsCiAgICAgICAgICAgICAgICBoZWxwZXIsCiAgICAgICAgICAgICkKICAgICAgICAgICAgcmV0dXJuIEZhbHNlCgogICAgICAgIHJlc3VsdCA9IF9zdWJwcm9jZXNzLnJ1bigKICAgICAgICAgICAgWwogICAgICAgICAgICAgICAgaGVscGVyLAogICAgICAgICAgICAgICAgbmFtZSwKICAgICAgICAgICAgXSwKICAgICAgICAgICAgc3Rkb3V0PV9zdWJwcm9jZXNzLlBJUEUsCiAgICAgICAgICAgIHN0ZGVycj1fc3VicHJvY2Vzcy5TVERPVVQsCiAgICAgICAgICAgIHRleHQ9VHJ1ZSwKICAgICAgICAgICAgY2hlY2s9RmFsc2UsCiAgICAgICAgICAgIHRpbWVvdXQ9MjQwLAogICAgICAgICkKCiAgICAgICAgcHJvZmlsZSA9ICgKICAgICAgICAgICAgZiIvcm9vdC97bmFtZX0ub3ZwbiIKICAgICAgICApCgogICAgICAgIG9rID0gKAogICAgICAgICAgICByZXN1bHQucmV0dXJuY29kZSA9PSAwCiAgICAgICAgICAgIGFuZCBfb3MucGF0aC5pc2ZpbGUocHJvZmlsZSkKICAgICAgICAgICAgYW5kIF9vcy5wYXRoLmdldHNpemUocHJvZmlsZSkgPiA1MDAKICAgICAgICApCgogICAgICAgIGlmIG5vdCBvazoKICAgICAgICAgICAgbG9nZ2VyLmVycm9yKAogICAgICAgICAgICAgICAgIlByb2ZpbGUgYnVpbGRlciBmYWlsZWQgIgogICAgICAgICAgICAgICAgImZvciAlcyByYz0lcyBvdXRwdXQ9JXMiLAogICAgICAgICAgICAgICAgbmFtZSwKICAgICAgICAgICAgICAgIHJlc3VsdC5yZXR1cm5jb2RlLAogICAgICAgICAgICAgICAgKHJlc3VsdC5zdGRvdXQgb3IgIiIpWy0yMDAwOl0sCiAgICAgICAgICAgICkKCiAgICAgICAgcmV0dXJuIG9rCgogICAgZXhjZXB0IF9zdWJwcm9jZXNzLlRpbWVvdXRFeHBpcmVkOgogICAgICAgIGxvZ2dlci5lcnJvcigKICAgICAgICAgICAgIlByb2ZpbGUgYnVpbGRlciB0aW1lb3V0OiAlcyIsCiAgICAgICAgICAgIG5hbWUsCiAgICAgICAgKQogICAgICAgIHJldHVybiBGYWxzZQoKICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZXhjOgogICAgICAgIGxvZ2dlci5leGNlcHRpb24oCiAgICAgICAgICAgICJQcm9maWxlIGJ1aWxkZXIgZmFpbGVkICVzOiAlcyIsCiAgICAgICAgICAgIG5hbWUsCiAgICAgICAgICAgIGV4YywKICAgICAgICApCiAgICAgICAgcmV0dXJuIEZhbHNlCicnJwoKCmxpbmVzID0gc291cmNlLnNwbGl0bGluZXMoCiAgICBrZWVwZW5kcz1UcnVlCikKCmxpbmVzWwogICAgdGFyZ2V0LmxpbmVubyAtIDE6CiAgICB0YXJnZXQuZW5kX2xpbmVubwpdID0gWwogICAgcmVwbGFjZW1lbnQKICAgICsgIlxuXG4iCl0KCnAud3JpdGVfdGV4dCgKICAgICIiLmpvaW4obGluZXMpLAogICAgZW5jb2Rpbmc9InV0Zi04IiwKKQoKcHJpbnQoCiAgICAiT1ZOT0RFX0NSRUFURV9VU0VSX1dSQVBQRVI9UEFTUyIKKQo=' | base64 -d >/tmp/patch-ov-user-wrapper.py
python3 /tmp/patch-ov-user-wrapper.py "$NEW"
rm -f /tmp/patch-ov-user-wrapper.py
python3 -m py_compile "$NEW/core/service/user_managment.py"
stage 61 profile_builder "Profile builder verified"

stage 62 router_capability "Installing disabled Router/OpenVPN capability"
{router_capability}
stage 63 router_capability "Router/OpenVPN capability installed (listener remains disabled)"

stage 65 dependencies "Installing OV Node dependencies"
cd "$NEW"; /root/.local/bin/uv sync
stage 75 service "Activating OV Node service"
if [[ -d /opt/ov-node ]]; then cp -a /opt/ov-node "$BACKUP"; fi
changed=1
rm -rf /opt/ov-node; mv "$NEW" /opt/ov-node

# PVNETWORK_RUNTIME_COMPAT_V1
if [[ -f /opt/ov-node/core/setting/core.py ]]; then
    sed -i \
        's|/etc/openvpn/server/client-common.txt|/etc/openvpn/server/client-template.txt|g' \
        /opt/ov-node/core/setting/core.py
fi

# Make dashboard helpers fail-safe and ensure status exists first.
if [[ -f /opt/ov-node/core/routers/router.py ]] \
   && grep -q '_pvnetwork_dashboard_network_snapshot' \
        /opt/ov-node/core/routers/router.py
then
    sed -i \
        '/^[[:space:]]*status.update(_pvnetwork_dashboard_network_snapshot())/d' \
        /opt/ov-node/core/routers/router.py

    sed -i \
        '/^[[:space:]]*status.update(_pvnetwork_openvpn_online_snapshot())/d' \
        /opt/ov-node/core/routers/router.py

    sed -i \
        '/^[[:space:]]*status = /a\
    try:\
        status.update(_pvnetwork_dashboard_network_snapshot())\
        status.update(_pvnetwork_openvpn_online_snapshot())\
    except Exception:\
        pass' \
        /opt/ov-node/core/routers/router.py
fi

python3 -m py_compile \
    /opt/ov-node/core/setting/core.py \
    /opt/ov-node/core/routers/router.py
cat >/etc/systemd/system/ov-node.service <<'EOF'
[Unit]
Description=OV Node API
After=network-online.target openvpn-server@server.service
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=/opt/ov-node
ExecStart=/root/.local/bin/uv run main.py
Restart=always
RestartSec=3
User=root
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=no
Environment="UV_CACHE_DIR=/var/cache/ov-node/uv"
ReadWritePaths=/var/cache/ov-node
ExecStartPre=/usr/bin/install -d -o root -g root -m 0755 /var/cache/ov-node/uv
Environment=PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
[Install]
WantedBy=multi-user.target
EOF
if [ -f /opt/ov-node/main.py ]; then
    sed -i 's/reload[[:space:]]*=[[:space:]]*True/reload=False/g' /opt/ov-node/main.py

    if grep -Eq 'reload[[:space:]]*=[[:space:]]*True' /opt/ov-node/main.py; then
        echo "ERROR: Could not disable Uvicorn reload"
        exit 1
    fi
fi

install -d -o root -g root -m 0755 /var/cache/ov-node
install -d -o root -g root -m 0755 /var/cache/ov-node/uv
systemctl daemon-reload
systemctl enable ov-node
systemctl reset-failed ov-node || true
systemctl restart ov-node
stage 84 firewall "Applying persistent IPv4 and IPv6 firewall rules"
iptables -C INPUT -i lo -p tcp --dport {api_port} -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i lo -p tcp --dport {api_port} -j ACCEPT
iptables -C INPUT -p tcp -s {panel_ip} --dport {api_port} -j ACCEPT 2>/dev/null || iptables -I INPUT 2 -p tcp -s {panel_ip} --dport {api_port} -j ACCEPT
iptables -C INPUT -p tcp --dport {api_port} -j DROP 2>/dev/null || iptables -A INPUT -p tcp --dport {api_port} -j DROP
if command -v ip6tables >/dev/null; then
  ip6tables -C INPUT -i lo -p tcp --dport {api_port} -j ACCEPT 2>/dev/null || ip6tables -I INPUT 1 -i lo -p tcp --dport {api_port} -j ACCEPT
  ip6tables -C INPUT -p tcp --dport {api_port} -j DROP 2>/dev/null || ip6tables -A INPUT -p tcp --dport {api_port} -j DROP
fi
netfilter-persistent save
stage 90 local_health "Waiting for local API health"
for attempt in $(seq 1 30); do curl -fsS --connect-timeout 2 --max-time 5 http://127.0.0.1:{api_port}/openapi.json >/dev/null && ready=1 && break; sleep 2; done
[[ ${{ready:-0}} -eq 1 ]] || {{ journalctl -u ov-node -n 60 --no-pager; exit 23; }}
stage 92 domain_history "Skipping optional DNS domain history during node bootstrap"
echo "PVNETWORK_WARN|Domain history is optional and has been deferred; core node installation continues"
domain_changed=0

systemctl is-active --quiet openvpn-server@server || systemctl is-active --quiet openvpn
rm -rf "$BACKUP" "$DOMAIN_BACKUP" /tmp/ov-node.tar.gz /tmp/ov-domain-response.json
changed=0
domain_changed=0
trap - EXIT
stage 94 remote_complete "Remote installation completed"
echo DEPLOY_OK
'''


def deploy_node(*, host: str, ssh_port: int, username: str, password: str,
                api_port: int, ovpn_port: int, protocol: str, panel_ip: str,
                expected_fingerprint: str | None = None,
                reporter: Callable[[int, str, str, str], None] | None = None) -> DeployResult:
    host = _valid_host(host)
    panel_ip = str(ipaddress.ip_address(panel_ip.strip()))
    if not all(1 <= p <= 65535 for p in (ssh_port, api_port, ovpn_port)):
        raise ValueError("Invalid port")
    if protocol not in {"tcp", "udp"}:
        raise ValueError("Protocol must be tcp or udp")
    if not username or len(username) > 64 or "\n" in username:
        raise ValueError("Invalid SSH username")
    if not password:
        raise ValueError("SSH password is required")
    report = reporter or (lambda *_: None)
    api_key = secrets.token_urlsafe(30)
    client = paramiko.SSHClient()
    configure_ssh_client(
        client,
        expected_fingerprint=expected_fingerprint,
    )
    output: list[str] = []
    report(2, "ssh", "Connecting to target server", "info")
    try:
        client.connect(hostname=host, port=ssh_port, username=username, password=password,
                       timeout=20, banner_timeout=20, auth_timeout=20,
                       allow_agent=False, look_for_keys=False)
        transport = client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport unavailable")
        fingerprint = sha256_fingerprint(transport.get_remote_server_key())
        report(4, "ssh", f"SSH connected; host fingerprint {fingerprint}", "ok")
        channel = transport.open_session(timeout=20)
        channel.exec_command("bash -s")  # nosec B601
        channel.sendall(_stage_script(api_port, ovpn_port, protocol, api_key, panel_ip).encode())
        channel.shutdown_write()
        deadline = time.monotonic() + DEPLOY_TIMEOUT
        stdout_buffer = ""
        stderr_buffer = ""
        while not channel.exit_status_ready() or channel.recv_ready() or channel.recv_stderr_ready():
            if time.monotonic() > deadline:
                channel.close()
                raise TimeoutError(f"Deployment exceeded {DEPLOY_TIMEOUT} seconds")
            if channel.recv_ready():
                stdout_buffer += channel.recv(65536).decode("utf-8", errors="replace")
                lines = stdout_buffer.split("\n")
                stdout_buffer = lines.pop()
                for line in lines:
                    if line.startswith("PVNETWORK_STAGE|"):
                        _, pct, stage, message = line.split("|", 3)
                        report(int(pct), stage, message, "info")
                    elif line.strip():
                        output.append(line.replace(api_key, "[REDACTED]")[-1000:])
            if channel.recv_stderr_ready():
                stderr_buffer += channel.recv_stderr(65536).decode("utf-8", errors="replace")
            time.sleep(.05)
        code = channel.recv_exit_status()
        tail = (stdout_buffer + "\n" + stderr_buffer).replace(api_key, "[REDACTED]")
        output.extend(x[-1000:] for x in tail.splitlines() if x.strip())
        output = output[-80:]
        if code != 0 or not any("DEPLOY_OK" in x for x in output):
            raise RuntimeError("Remote installation failed: " + " | ".join(output[-10:]))
    finally:
        client.close()
    return DeployResult(host, api_port, api_key, ovpn_port, protocol, fingerprint, output)
