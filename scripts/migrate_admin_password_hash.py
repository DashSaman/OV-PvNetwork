#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def parse(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def rewrite(path: Path, *, plaintext: str | None = None) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    values = parse(lines)
    current_hash = values.get("ADMIN_PASSWORD_HASH", "").strip()
    legacy = (plaintext if plaintext is not None else values.get("ADMIN_PASSWORD", "")).strip()
    if not current_hash and not legacy:
        raise RuntimeError("No main-admin credential is available to migrate")
    if not current_hash:
        current_hash = hash_password(legacy)

    out: list[str] = []
    wrote_hash = False
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("ADMIN_PASSWORD=") or stripped.startswith("ADMIN_PASSWORD ="):
            continue
        if stripped.startswith("ADMIN_PASSWORD_HASH=") or stripped.startswith("ADMIN_PASSWORD_HASH ="):
            if not wrote_hash:
                out.append(f"ADMIN_PASSWORD_HASH={current_hash}")
                wrote_hash = True
            continue
        out.append(raw)
    if not wrote_hash:
        insert_at = 1 if out and out[0].lstrip().startswith("ADMIN_USERNAME=") else 0
        out.insert(insert_at, f"ADMIN_PASSWORD_HASH={current_hash}")

    new_text = "\n".join(out).rstrip() + "\n"
    old_text = path.read_text(encoding="utf-8")
    if new_text == old_text:
        os.chmod(path, 0o600)
        return False

    tmp = path.with_name(path.name + ".admin-hash.tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate PVNetwork main-admin password to a one-way bcrypt hash")
    ap.add_argument("--env", default="/opt/pvnetwork-panel/.env")
    ap.add_argument("--password-stdin", action="store_true")
    args = ap.parse_args()
    env_path = Path(args.env)
    if not env_path.is_file():
        raise SystemExit(f"Environment file not found: {env_path}")
    plaintext = None
    if args.password_stdin:
        import sys
        plaintext = sys.stdin.readline().rstrip("\r\n")
        if not plaintext:
            raise SystemExit("Empty password on stdin")
    changed = rewrite(env_path, plaintext=plaintext)
    print("ADMIN_PASSWORD_HASH_MIGRATION=UPDATED" if changed else "ADMIN_PASSWORD_HASH_MIGRATION=ALREADY_SECURE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
