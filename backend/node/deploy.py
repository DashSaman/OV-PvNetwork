from __future__ import annotations

import base64
import gzip
import hashlib
import io
import ipaddress
import json
import os
import re
import secrets
import threading
import tarfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import paramiko
from pydantic import ValidationError

from backend.security_ssh import configure_ssh_client, sha256_fingerprint


DEPLOY_TIMEOUT = int(os.getenv("PVNETWORK_NODE_DEPLOY_TIMEOUT", "900"))
JOB_TTL = int(os.getenv("PVNETWORK_NODE_DEPLOY_JOB_TTL", "86400"))
JOB_DIR = Path(__file__).resolve().parents[2] / "data" / "deploy-jobs"
_jobs: dict[str, "DeployJob"] = {}
_jobs_lock = threading.RLock()
_host_locks: dict[str, threading.Lock] = {}


def build_native_node_bundle() -> tuple[bytes,str]:
    """Build a deterministic source-only payload without any installed node."""
    root=Path(__file__).resolve().parents[2]
    required=['VERSION','ops/toolchain.json','node-agent/VERSION','node-agent/LICENSE',
              'node-agent/pyproject.toml','node-agent/uv.lock',
              'scripts/pvnetwork_node_install.py','scripts/pvnetwork_node_lifecycle.py','scripts/pvnetwork_node_backup.py','scripts/pvnetwork_install.py',
              'scripts/pvnetwork-build-client-profile','scripts/pvnetwork-router-openvpn',
              'scripts/pvnetwork-router-auth','scripts/pvnetwork-domain-collector',
              'scripts/pvnetwork-session-connect','scripts/pvnetwork-session-disconnect',
              'ops/systemd/pvnetwork-node.service','ops/systemd/pvnetwork-domain-collector.service']
    paths=set(required)
    # Collect only distributable source, never local runtime/env backup files.
    paths.update({'node-agent/main.py','node-agent/README.md'})
    for p in (root/'node-agent/core').rglob('*.py'):
        if p.is_file() and not any(x in {'.venv','__pycache__','.git'} for x in p.parts):paths.add(p.relative_to(root).as_posix())
    if any(not (root/name).is_file() or (root/name).is_symlink() for name in required):raise RuntimeError('native node source bundle is incomplete')
    files={}
    for name in sorted(paths):
        p=root/name
        if p.is_symlink() or p.name=='.env' or p.suffix.lower() in {'.key','.pem','.crt','.db','.ovpn'}:raise ValueError('private/linked node source material refused')
        files[name]=p.read_bytes().replace(b'\r\n',b'\n')
    if files['VERSION'].strip()!=files['node-agent/VERSION'].strip():raise ValueError('node/controller source versions differ')
    files['SOURCE-MANIFEST.json']=json.dumps({'format':'pvnetwork-node-source-v1','version':files['VERSION'].decode().strip(),'sha256':{name:hashlib.sha256(value).hexdigest() for name,value in files.items()}},sort_keys=True).encode()
    output=io.BytesIO()
    with gzip.GzipFile(fileobj=output,mode='wb',mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as archive:
        for name,value in files.items():
            member=tarfile.TarInfo(name);member.size=len(value);member.mode=0o755 if name.startswith('scripts/') else 0o644
            archive.addfile(member,io.BytesIO(value))
    payload=output.getvalue()
    if len(payload)>16*1024**2:raise ValueError('native source payload size limit exceeded')
    return payload,hashlib.sha256(payload).hexdigest()


@dataclass
class DeployResult:
    address: str
    api_port: int
    api_key: str
    ovpn_port: int
    protocol: str
    fingerprint: str
    log: list[str]
    transaction_id: str = ''


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
    JOB_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(JOB_DIR,0o700)
    tmp = JOB_DIR / f".{job.id}.tmp"
    target = JOB_DIR / f"{job.id}.json"
    with tmp.open('w',encoding='utf-8') as handle:
        os.chmod(tmp,0o600);handle.write(json.dumps(job.public(),ensure_ascii=False));handle.flush();os.fsync(handle.fileno())
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
            job.error = "Deployment was interrupted; inspect the remote owned transaction before retry"
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


def fail_job(job: DeployJob, exc: Exception, secret_values=()) -> None:
    if isinstance(exc,ValidationError):
        message='Invalid deployment configuration: '+ '; '.join('.'.join(str(x) for x in item['loc'])+': '+item['msg'] for item in exc.errors(include_input=False,include_context=False,include_url=False))
    elif isinstance(exc,(RuntimeError,ValueError,TimeoutError,paramiko.SSHException)):
        message=str(exc)
    else:
        # Database exceptions can contain SQL parameter tuples and credentials.
        message=type(exc).__name__+': deployment failed; inspect administrator diagnostics'
    for value in secret_values:
        if value:message=message.replace(str(value),'[REDACTED]')
    message=re.sub(r'pvn_tls_v1_[A-Za-z0-9_-]+','[REDACTED]',message)
    message = message.replace("\n", " ")[:1500]
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
python3 /tmp/pvnetwork-node-router-patch.py {node_root} --user-lifecycle-only
python3 /tmp/pvnetwork-node-router-patch.py {node_root} --router-only
python3 -m py_compile {node_root}/core/service/user_managment.py {router_py} {module_py}
grep -q 'def get_user_identity_state' {node_root}/core/service/user_managment.py
grep -q '/user/{{name}}/identity' {router_py}
mv -f /usr/local/sbin/pvnetwork-router-openvpn.new /usr/local/sbin/pvnetwork-router-openvpn
mv -f /usr/local/libexec/pvnetwork-router-auth.new /usr/local/libexec/pvnetwork-router-auth
rm -f /tmp/pvnetwork-node-router-patch.py
# Capability files are inert until an explicit Router/OpenVPN enable API call.
'''


def _panel_firewall_mode(panel_ip: str | None) -> tuple[str, str]:
    """Classify the requested node-side allowlist source.

    Returns ("explicit", "<ip>") for a valid IP literal and ("auto", "") when
    the caller supplied nothing usable (empty, hostname behind a proxy/CDN, or
    malformed input). Auto mode derives the true panel source IP on the node
    from the SSH session itself, which always matches the path the panel API
    calls will take.
    """
    value = str(panel_ip or "").strip()
    if value:
        try:
            return "explicit", str(ipaddress.ip_address(value))
        except ValueError:
            pass
    return "auto", ""


def deploy_node(*, host: str, ssh_port: int, username: str, password: str | None,
                api_port: int, ovpn_port: int, protocol: str,
                panel_ip: str | None = None, mode: str = 'fresh',
                panel_url: str = '', panel_ca_pem: str | None = None,
                adopted_api_key: str | None = None,
                ssh_private_key: str | None = None, ssh_key_passphrase: str | None = None,
                expected_fingerprint: str | None = None,
                reporter: Callable[[int, str, str, str], None] | None = None) -> DeployResult:
    from backend.node import native_deploy, tls, deploy_probe
    host = _valid_host(host)
    if not all(isinstance(p,int) and 1 <= p <= 65535 for p in (ssh_port,api_port,ovpn_port)):
        raise ValueError('Invalid node port')
    if protocol not in {'tcp','udp'} or mode not in {'fresh','adopt'}:
        raise ValueError('Explicit valid protocol and installation mode required')
    if not username or not __import__('re').fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}',username):
        raise ValueError('Invalid SSH username')
    if not password and not ssh_private_key:
        raise ValueError('SSH password or private key is required')
    report = reporter or (lambda *_: None)
    payload,digest=build_native_node_bundle()
    # Fits the existing creation API's 40-character limit without a schema migration.
    # The random portion retains 168 bits of entropy.
    api_key=adopted_api_key if mode=='adopt' and adopted_api_key else tls.KEY_PREFIX+secrets.token_urlsafe(21)
    configuration={'mode':mode,'api_port':api_port,'ovpn_port':ovpn_port,'protocol':protocol,
                   'host':host,'api_key':api_key,'panel_url':panel_url}
    if _panel_firewall_mode(panel_ip)[0]=='explicit':configuration['panel_source_ip']=panel_ip
    if panel_ca_pem:configuration['panel_ca_pem']=panel_ca_pem
    nonce=deploy_probe.register(api_key);configuration['controller_probe_nonce']=nonce
    try:
        result,fingerprint=native_deploy.install(host=host,ssh_port=ssh_port,username=username,password=password,
                      key=ssh_private_key,passphrase=ssh_key_passphrase,fingerprint=expected_fingerprint,
                      configuration=configuration,source=payload,digest=digest,report=report,timeout=DEPLOY_TIMEOUT)
    finally:deploy_probe.discard(api_key,nonce)
    try:
        tls.save_trust(host,api_port,result['ca_pem'],api_key)
    except Exception:
        native_deploy.control(action='rollback',transaction_id=result['transaction_id'],host=host,
                              ssh_port=ssh_port,username=username,password=password,key=ssh_private_key,
                              passphrase=ssh_key_passphrase,fingerprint=fingerprint)
        raise
    return DeployResult(host,api_port,api_key,ovpn_port,protocol,fingerprint,
                        ['Verified native source SHA256 '+digest],result['transaction_id'])
