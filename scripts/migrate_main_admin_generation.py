#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def rewrite_env_key_atomic(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced = False
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            if not replaced:
                out.append(f"{key}={value}")
                replaced = True
            continue
        out.append(raw)
    if not replaced:
        insert_at = 1 if out and out[0].lstrip().startswith("ADMIN_USERNAME=") else 0
        out.insert(insert_at, f"{key}={value}")
    tmp = path.with_name(path.name + ".generation.tmp")
    tmp.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    with tmp.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def ensure_generation(env_path: Path) -> str:
    values = parse_env(env_path)
    current = values.get("MAIN_ADMIN_AUTH_GENERATION", "").strip()
    if current:
        os.chmod(env_path, 0o600)
        return current
    value = secrets.token_urlsafe(24)
    rewrite_env_key_atomic(env_path, "MAIN_ADMIN_AUTH_GENERATION", value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure PVNetwork main-admin auth generation")
    parser.add_argument("--env", default="/opt/pvnetwork-panel/.env")
    args = parser.parse_args()
    env_path = Path(args.env)
    if not env_path.is_file():
        raise SystemExit(f"Environment file not found: {env_path}")
    ensure_generation(env_path)
    print("MAIN_ADMIN_AUTH_GENERATION=READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
