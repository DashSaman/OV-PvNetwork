#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(os.getenv("PVNETWORK_APP_DIR", "/opt/pvnetwork-panel"))
VENV_PYTHON = APP_DIR / ".venv/bin/python"
if __name__ == "__main__" and VENV_PYTHON.is_file() and Path(sys.prefix).resolve() != (APP_DIR / ".venv").resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import jwt
from backend import panel_runtime_settings as runtime

BACKUP_ROOT = Path(
    os.getenv(
        "PVNETWORK_RUNTIME_SETTINGS_BACKUPS",
        "/var/backups/pvnetwork-panel/runtime-settings",
    )
)
CANARY_PORT = 19002
REDIRECT_GRACE_SECONDS = 300
ALLOWED_RESTARTS = {"pvnetwork-panel.service"}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix().encode()
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def update_job(change_id: str, **changes) -> dict:
    current = runtime.read_job_state(change_id) or {}
    current.update(changes)
    current["updated_at"] = int(time.time())
    runtime.write_job_state(change_id, current)
    return current


def restart_service(name: str) -> None:
    if name not in ALLOWED_RESTARTS:
        raise RuntimeError(f"forbidden service restart: {name}")
    subprocess.run(
        ["systemctl", "restart", name],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )


def _rename_exchange(left: Path, right: Path) -> None:
    if left.stat().st_dev != right.stat().st_dev:
        raise RuntimeError("atomic directory exchange requires the same filesystem")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise RuntimeError("renameat2(RENAME_EXCHANGE) is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    rc = renameat2(
        -100,
        os.fsencode(left),
        -100,
        os.fsencode(right),
        2,
    )
    if rc != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), f"{left} <-> {right}")


def exchange_directories(left: Path, right: Path) -> None:
    if not left.is_dir() or not right.is_dir():
        raise RuntimeError("both exchange paths must be directories")
    _rename_exchange(left, right)


def build_frontend(candidate_env: Path, staging_dir: Path) -> Path:
    frontend = APP_DIR / "frontend"
    vite = frontend / "node_modules/.bin/vite"
    if not vite.is_file():
        raise RuntimeError("frontend dependencies are missing: vite not found")
    values = parse_env(candidate_env)
    out_dir = staging_dir / "dist"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    env = os.environ.copy()
    env.update(values)
    env["URLPATH"] = values["URLPATH"]
    env["VITE_URLPATH"] = values.get("VITE_URLPATH", values["URLPATH"])
    env["PVNETWORK_BUILD_OUTDIR"] = str(out_dir)
    subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=240,
    )
    if not (out_dir / "index.html").is_file():
        raise RuntimeError("candidate frontend build did not produce index.html")
    return out_dir


def start_candidate(candidate_env: Path, dist: Path, staging_dir: Path):
    values = parse_env(candidate_env)
    env = os.environ.copy()
    env.update(values)
    env.update(
        HOST="127.0.0.1",
        PORT=str(CANARY_PORT),
        PVNETWORK_FRONTEND_DIST=str(dist),
        PYTHONUNBUFFERED="1",
    )
    python = APP_DIR / ".venv/bin/python"
    if not python.is_file():
        raise RuntimeError("panel virtualenv python is missing")
    log_path = staging_dir / "candidate.log"
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    log_handle = os.fdopen(log_fd, "ab", buffering=0)
    try:
        process = subprocess.Popen(
            [str(python), str(APP_DIR / "main.py")],
            cwd=APP_DIR,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log_handle.close()
    return process


def stop_candidate(process) -> None:
    if process is None or not hasattr(process, "poll"):
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _http_get(url: str, headers: dict[str, str] | None = None, timeout: float = 2.0):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()
    except OSError:
        return 0, b""


def _asset_path(html: bytes) -> str | None:
    text = html.decode("utf-8", errors="replace")
    match = re.search(r'(?:src|href)=["\']([^"\']*/assets/[^"\']+)["\']', text)
    return match.group(1) if match else None


def _main_admin_token(values: dict[str, str]) -> str:
    return jwt.encode(
        {
            "sub": values["ADMIN_USERNAME"],
            "type": "main_admin",
            "gen": values["MAIN_ADMIN_AUTH_GENERATION"],
            "exp": int(time.time()) + 60,
        },
        values["JWT_SECRET_KEY"],
        algorithm="HS256",
    )


def _verify_once(port: int, values: dict[str, str]) -> bool:
    base = f"http://127.0.0.1:{port}"
    status, _ = _http_get(f"{base}/healthz")
    if status != 200:
        return False
    path = values["URLPATH"].strip("/")
    status, html = _http_get(f"{base}/{path}")
    if status != 200:
        return False
    asset = _asset_path(html)
    if not asset:
        return False
    asset_url = f"{base}{asset}" if asset.startswith("/") else f"{base}/{path}/{asset}"
    status, _ = _http_get(asset_url)
    if status != 200:
        return False
    token = _main_admin_token(values)
    status, _ = _http_get(
        f"{base}/api/security/panel-settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    return status == 200


def _wait_verify(port: int, values: dict[str, str], timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _verify_once(port, values):
            return True
        time.sleep(0.5)
    return False


def verify_candidate(process, candidate_env: Path, dist: Path) -> bool:
    if process is not None and hasattr(process, "poll") and process.poll() is not None:
        return False
    values = parse_env(candidate_env)
    return _wait_verify(CANARY_PORT, values, 20.0)


def verify_canonical(job: dict) -> bool:
    live_env = APP_DIR / ".env"
    values = parse_env(live_env)
    port = int(values.get("PORT", "19001"))
    return _wait_verify(port, values, 30.0)


def _safe_failure_reason(exc: BaseException) -> str:
    text = str(exc).replace("\r", " ").replace("\n", " ").strip()
    return text[:300] or exc.__class__.__name__


def _copy_private(src: Path, dst: Path) -> None:
    shutil.copy2(src, dst)
    os.chmod(dst, 0o600)


def _service_metadata() -> str:
    try:
        result = subprocess.run(
            ["systemctl", "show", "pvnetwork-panel.service", "-p", "MainPID", "-p", "NRestarts", "-p", "ExecStart"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
        return result.stdout
    except Exception as exc:
        return f"metadata unavailable: {exc.__class__.__name__}\n"


def create_backup(change_id: str, live_env: Path, live_dist: Path) -> Path:
    backup = BACKUP_ROOT / change_id
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True, mode=0o700)
    _copy_private(live_env, backup / ".env")
    shutil.copytree(live_dist, backup / "dist")
    transition_backup = backup / "panel-path-transition.json"
    if runtime.TRANSITION_FILE.is_file():
        _copy_private(runtime.TRANSITION_FILE, transition_backup)
    (backup / "service-metadata.txt").write_text(_service_metadata(), encoding="utf-8")
    os.chmod(backup / "service-metadata.txt", 0o600)
    checksums = {
        "env_sha256": sha256_file(live_env),
        "dist_sha256": sha256_tree(live_dist),
        "transition_present": transition_backup.is_file(),
    }
    (backup / "checksums.json").write_text(
        json.dumps(checksums, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(backup / "checksums.json", 0o600)
    return backup


def _restore_env(backup_env: Path, live_env: Path) -> None:
    tmp = live_env.with_name(f".{live_env.name}.rollback.{os.getpid()}")
    shutil.copy2(backup_env, tmp)
    os.chmod(tmp, 0o600)
    with tmp.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(tmp, live_env)


def _restore_transition(backup: Path) -> None:
    saved = backup / "panel-path-transition.json"
    if saved.is_file():
        runtime.TRANSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = runtime.TRANSITION_FILE.with_name(".panel-path-transition.rollback.tmp")
        shutil.copy2(saved, tmp)
        os.chmod(tmp, 0o600)
        os.replace(tmp, runtime.TRANSITION_FILE)
    else:
        runtime.TRANSITION_FILE.unlink(missing_ok=True)



def _session_factory_default():
    from backend.db.engine import SessionLocal
    return SessionLocal()


def migrate_principal_security(job: dict, *, forward: bool, session_factory=None) -> None:
    principal_id = job.get("principal_security_id")
    old_username = str(job.get("old_username") or "")
    new_username = str(job.get("new_username") or old_username)
    if not principal_id or old_username == new_username:
        return
    from backend.db.models import PrincipalSecurity
    factory = session_factory or _session_factory_default
    db = factory()
    source = old_username if forward else new_username
    target = new_username if forward else old_username
    try:
        row = db.get(PrincipalSecurity, int(principal_id))
        if row is None:
            return
        if row.principal_type != "main_admin":
            raise RuntimeError("principal security row is not main_admin")
        if row.username == target:
            return
        if row.username != source:
            raise RuntimeError("principal security username changed concurrently")
        row.username = target
        row.updated_at = int(time.time())
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def write_terminal_audit(job: dict, result: str, *, session_factory=None) -> None:
    audit_actor = str(job.get("audit_actor") or "").strip()
    if not audit_actor:
        return
    from backend.db.models import AuditLog
    change_id = str(job.get("change_id") or "unknown")[:40]
    terminal = "complete" if result == "complete" else "rollback"
    request_id = f"settings-{change_id}-{terminal}"[:64]
    factory = session_factory or _session_factory_default
    db = factory()
    try:
        if db.query(AuditLog).filter(AuditLog.request_id == request_id).first():
            return
        old_path = str(job.get("old_path") or "")[:64]
        new_path = str(job.get("new_path") or old_path)[:64]
        username_changed = str(job.get("old_username") or "") != str(job.get("new_username") or "")
        resource = (
            f"panel-settings:{change_id}:path={old_path}->{new_path}:"
            f"username={'changed' if username_changed else 'unchanged'}:result={result}"
        )[:512]
        audit_values = dict(
            actor=audit_actor[:128],
            actor_type="main_admin", action="SETTINGS_APPLY", resource=resource,
            status_code=200 if result == "complete" else 500,
            success=result == "complete", ip_address=None, user_agent=None,
            request_id=request_id, duration_ms=0, created_at=int(time.time()),
        )
        if db.get_bind().dialect.name == "sqlite":
            last = db.query(AuditLog.id).order_by(AuditLog.id.desc()).first()
            audit_values["id"] = int(last[0]) + 1 if last else 1
        db.add(AuditLog(**audit_values))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_change(change_id: str, staging_dir: Path, lock_fd: int) -> dict:
    job = runtime.read_job_state(change_id)
    if not job:
        raise RuntimeError("panel settings job not found")
    if job.get("status") in {"complete", "rolled_back"}:
        return job

    live_env = APP_DIR / ".env"
    live_dist = APP_DIR / "frontend/dist"
    candidate_env = staging_dir / "candidate.env"
    candidate = None
    backup: Path | None = None
    dist_switched = False
    env_switched = False
    principal_migrated = False

    try:
        if sha256_file(live_env) != str(job.get("expected_env_sha256") or ""):
            raise RuntimeError("live environment changed before apply")
        update_job(change_id, status="building")
        candidate_dist = build_frontend(candidate_env, staging_dir)

        update_job(change_id, status="canary")
        candidate = start_candidate(candidate_env, candidate_dist, staging_dir)
        if not verify_candidate(candidate, candidate_env, candidate_dist):
            raise RuntimeError("candidate panel verification failed")

        if sha256_file(live_env) != str(job.get("expected_env_sha256") or ""):
            raise RuntimeError("live environment changed during candidate build")
        backup = create_backup(change_id, live_env, live_dist)

        update_job(change_id, status="switching")
        exchange_directories(live_dist, candidate_dist)
        dist_switched = True
        os.chmod(candidate_env, 0o600)
        with candidate_env.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(candidate_env, live_env)
        env_switched = True
        if job.get("username_changed"):
            migrate_principal_security(job, forward=True)
            principal_migrated = True

        runtime.write_transition_state(
            {
                "old_path": job["old_path"],
                "new_path": job["new_path"],
                "redirect_expires_at": int(time.time()) + REDIRECT_GRACE_SECONDS,
                "change_id": change_id,
            }
        )
        restart_service("pvnetwork-panel.service")
        update_job(change_id, status="verifying")
        if not verify_canonical(job):
            raise RuntimeError("canonical panel verification failed")

        result = update_job(change_id, status="complete", failure_reason=None)
        try:
            write_terminal_audit(result, "complete")
        except Exception:
            result = update_job(change_id, audit_warning="terminal audit unavailable")
        return result
    except Exception as exc:
        failure = _safe_failure_reason(exc)
        if backup is not None and (dist_switched or env_switched):
            try:
                if dist_switched:
                    candidate_dist = staging_dir / "dist"
                    if live_dist.is_dir() and candidate_dist.is_dir():
                        exchange_directories(live_dist, candidate_dist)
                if env_switched:
                    _restore_env(backup / ".env", live_env)
                _restore_transition(backup)
                if principal_migrated:
                    migrate_principal_security(job, forward=False)
                    principal_migrated = False
                restart_service("pvnetwork-panel.service")
                verify_canonical({"old_path": job.get("old_path")})
            except Exception as rollback_exc:
                failure = f"{failure}; rollback failure: {_safe_failure_reason(rollback_exc)}"
        result = update_job(change_id, status="rolled_back", failure_reason=failure)
        try:
            write_terminal_audit(result, "rolled_back")
        except Exception:
            pass
        return result
    finally:
        stop_candidate(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a staged PVNetwork panel runtime settings change")
    parser.add_argument("--change-id", required=True)
    parser.add_argument("--staging-dir", required=True)
    parser.add_argument("--lock-fd", required=True, type=int)
    args = parser.parse_args()

    try:
        os.fstat(args.lock_fd)
    except OSError as exc:
        raise SystemExit(f"invalid inherited lock fd: {exc}") from exc

    staging = Path(args.staging_dir).resolve()
    if not staging.is_dir():
        raise SystemExit(f"staging directory not found: {staging}")
    try:
        result = run_change(args.change_id, staging, args.lock_fd)
        print(json.dumps({"change_id": args.change_id, "status": result.get("status")}))
        return 0 if result.get("status") == "complete" else 1
    finally:
        try:
            os.close(args.lock_fd)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
