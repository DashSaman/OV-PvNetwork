import asyncio
import hashlib
import io
import json
import os
import re
import secrets
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.auth.auth import get_current_user
from backend.schema.output import ResponseModel


router = APIRouter(prefix="/backups", tags=["Backups"])

BACKUP_ROOT = Path("/var/backups/pvnetwork-panel")
JOB_ROOT = Path("/var/lib/pvnetwork-panel/restore-jobs")
BACKUP_COMMAND = Path("/usr/local/sbin/pvnetwork-panel-backup")
RESTORE_COMMAND = Path("/usr/local/sbin/pvnetwork-panel-restore-job")
MAX_UPLOAD_BYTES = 240 * 1024 * 1024
BACKUP_ID_RE = re.compile(r"^\d{8}-\d{6}$")
JOB_ID_RE = re.compile(r"^[a-f0-9]{24}$")
_backup_lock = asyncio.Lock()


def _main_admin_only(user: dict) -> None:
    if user.get("type") != "main_admin":
        raise HTTPException(status_code=403, detail="Main administrator required")
    if user.get("auth_kind") == "api_token":
        raise HTTPException(status_code=403, detail="Interactive administrator login required")


def _backup_directory(backup_id: str) -> Path:
    if not BACKUP_ID_RE.fullmatch(backup_id):
        raise HTTPException(status_code=404, detail="Backup not found")
    directory = BACKUP_ROOT / backup_id
    if not directory.is_dir() or directory.is_symlink():
        raise HTTPException(status_code=404, detail="Backup not found")
    return directory


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_checksums(directory: Path) -> dict[str, str]:
    checksum_file = directory / "SHA256SUMS"
    if not checksum_file.is_file() or checksum_file.is_symlink():
        return {}
    expected: dict[str, str] = {}
    try:
        text = checksum_file.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError):
        return {}
    if len(text) > 65536:
        return {}
    for line in text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(r"[a-fA-F0-9]{64}", parts[0]):
            continue
        name = Path(parts[1].lstrip("* ")).name
        if name in {"database.dump", "env", "source.tar.gz"}:
            expected[name] = parts[0].lower()
    return expected


def _is_verified(directory: Path) -> bool:
    required = ("database.dump", "env")
    expected = _expected_checksums(directory)
    if not (directory / "RESTORE_TEST_OK").is_file():
        return False
    for name in required:
        path = directory / name
        if not path.is_file() or path.is_symlink() or name not in expected:
            return False
        if not secrets.compare_digest(_sha256(path), expected[name]):
            return False
    return True


def _backup_row(directory: Path) -> dict:
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and not path.is_symlink()
    ]
    total_size = sum(path.stat().st_size for path in files)
    try:
        created = datetime.strptime(directory.name, "%Y%m%d-%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        created = datetime.fromtimestamp(directory.stat().st_mtime, tz=timezone.utc)
    return {
        "id": directory.name,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "size_bytes": total_size,
        "verified": _is_verified(directory),
        "files": sorted(path.name for path in files),
    }


def _list_backup_directories() -> list[Path]:
    BACKUP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    return sorted(
        (
            path
            for path in BACKUP_ROOT.iterdir()
            if path.is_dir()
            and not path.is_symlink()
            and BACKUP_ID_RE.fullmatch(path.name)
        ),
        key=lambda path: path.name,
        reverse=True,
    )


def _build_download_archive(directory: Path, destination: Path) -> None:
    selected = ("database.dump", "env", "SHA256SUMS", "RESTORE_TEST_OK")
    root_name = f"pvnetwork-backup-{directory.name}"
    manifest = {
        "format": "pvnetwork-manual-backup-v1",
        "backup_id": directory.name,
        "created_at": _backup_row(directory)["created_at"],
        "restore_scope": "database-and-settings",
    }
    with tarfile.open(destination, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        payload = json.dumps(manifest, ensure_ascii=True, indent=2).encode("utf-8")
        info = tarfile.TarInfo(f"{root_name}/MANIFEST.json")
        info.size = len(payload)
        info.mode = 0o600
        info.mtime = int(datetime.now(tz=timezone.utc).timestamp())
        archive.addfile(info, io.BytesIO(payload))
        for name in selected:
            path = directory / name
            if path.is_file() and not path.is_symlink():
                archive.add(path, arcname=f"{root_name}/{name}", recursive=False)


def _write_status(job_directory: Path, payload: dict) -> None:
    job_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = job_directory / ".job.json.tmp"
    target = job_directory / "job.json"
    temporary.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(target)


@router.get("/", response_model=ResponseModel)
async def list_backups(user: dict = Depends(get_current_user)):
    _main_admin_only(user)
    rows = await asyncio.to_thread(
        lambda: [_backup_row(path) for path in _list_backup_directories()[:30]]
    )
    return ResponseModel(success=True, msg="Backups loaded", data={"backups": rows})


@router.post("/", response_model=ResponseModel)
async def create_backup(user: dict = Depends(get_current_user)):
    _main_admin_only(user)
    if not BACKUP_COMMAND.is_file():
        raise HTTPException(status_code=503, detail="Backup service is unavailable")
    if _backup_lock.locked():
        raise HTTPException(status_code=409, detail="A backup is already running")

    async with _backup_lock:
        before = {path.name for path in _list_backup_directories()}

        def run_backup():
            return subprocess.run(
                [
                    "/usr/bin/flock",
                    "-n",
                    "-E",
                    "75",
                    "/run/lock/pvnetwork-panel-manual-backup.lock",
                    str(BACKUP_COMMAND),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=900,
                check=False,
            )

        try:
            result = await asyncio.to_thread(run_backup)
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="Backup timed out") from exc
        if result.returncode == 75:
            raise HTTPException(status_code=409, detail="A backup is already running")
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="Backup verification failed")

        created = [path for path in _list_backup_directories() if path.name not in before]
        if not created:
            raise HTTPException(status_code=500, detail="Backup output was not created")
        row = _backup_row(created[0])
        if not row["verified"]:
            raise HTTPException(status_code=500, detail="Backup checksum verification failed")
        return ResponseModel(success=True, msg="Backup created successfully", data=row)


@router.get("/{backup_id}/download")
async def download_backup(backup_id: str, user: dict = Depends(get_current_user)):
    _main_admin_only(user)
    directory = _backup_directory(backup_id)
    if not await asyncio.to_thread(_is_verified, directory):
        raise HTTPException(status_code=409, detail="Backup is not verified")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f"pvnetwork-backup-{backup_id}-",
        suffix=".tar.gz",
        dir="/tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    os.chmod(temporary, 0o600)
    try:
        await asyncio.to_thread(_build_download_archive, directory, temporary)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Backup archive could not be created")

    return FileResponse(
        path=temporary,
        filename=f"pvnetwork-backup-{backup_id}.tar.gz",
        media_type="application/gzip",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(temporary.unlink, missing_ok=True),
    )


@router.post("/restore", response_model=ResponseModel, status_code=status.HTTP_202_ACCEPTED)
async def restore_backup(
    file: UploadFile = File(...),
    confirmation: str = Form(...),
    user: dict = Depends(get_current_user),
):
    _main_admin_only(user)
    if confirmation.strip() != "RESTORE":
        raise HTTPException(status_code=422, detail="Type RESTORE to confirm")
    if not RESTORE_COMMAND.is_file():
        raise HTTPException(status_code=503, detail="Restore service is unavailable")

    filename = Path(file.filename or "").name.lower()
    if not (filename.endswith(".tar.gz") or filename.endswith(".tgz")):
        raise HTTPException(status_code=422, detail="Only .tar.gz backup files are accepted")

    job_id = secrets.token_hex(12)
    job_directory = JOB_ROOT / job_id
    job_directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    archive = job_directory / "upload.tar.gz"
    total = 0
    try:
        with archive.open("xb") as destination:
            os.chmod(archive, 0o600)
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Backup file is too large")
                destination.write(chunk)
        if total == 0:
            raise HTTPException(status_code=422, detail="Backup file is empty")

        payload = {
            "job_id": job_id,
            "state": "queued",
            "step": "queued",
            "progress": 5,
            "message": "Restore queued",
        }
        _write_status(job_directory, payload)
        result = subprocess.run(
            [
                "/usr/bin/systemd-run",
                f"--unit=pvnetwork-panel-restore-{job_id}",
                "--property=Type=oneshot",
                "--collect",
                "--no-block",
                str(RESTORE_COMMAND),
                job_id,
                str(archive),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            _write_status(
                job_directory,
                {**payload, "state": "failed", "message": "Restore job could not start"},
            )
            raise HTTPException(status_code=500, detail="Restore job could not start")
    except HTTPException:
        archive.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return ResponseModel(success=True, msg="Restore started", data=payload)


@router.get("/restore/{job_id}", response_model=ResponseModel)
async def restore_status(job_id: str, user: dict = Depends(get_current_user)):
    _main_admin_only(user)
    if not JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(status_code=404, detail="Restore job not found")
    status_file = JOB_ROOT / job_id / "job.json"
    if not status_file.is_file() or status_file.is_symlink():
        raise HTTPException(status_code=404, detail="Restore job not found")
    try:
        payload = json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Restore status is unavailable") from exc
    return ResponseModel(success=True, msg="Restore status", data=payload)
