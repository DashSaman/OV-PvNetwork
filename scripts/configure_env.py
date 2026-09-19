#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import os
import secrets
from pathlib import Path

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def secret_key(length: int = 64) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode().rstrip("=")


def parse_env(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def set_values(lines: list[str], values: dict[str, str]) -> list[str]:
    found: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        replaced = False
        for key, value in values.items():
            if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                out.append(f"{key}={value}")
                found.add(key)
                replaced = True
                break
        if not replaced:
            out.append(line)
    for key, value in values.items():
        if key not in found:
            out.append(f"{key}={value}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Configure PVNetwork environment")
    ap.add_argument("--panel-dir", default="/opt/pvnetwork-panel")
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--path", default="dashboard")
    ap.add_argument("--subscription-path", default="sub")
    ap.add_argument("--subscription-url-prefix", default="")
    args = ap.parse_args()

    panel = Path(args.panel_dir)
    env_path = panel / ".env"
    example = panel / ".env.example"

    if not env_path.exists():
        if not example.exists():
            raise SystemExit(".env.example not found")
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    path = args.path.strip("/")
    sub_path = args.subscription_path.strip("/") or "sub"
    values = {
        "ADMIN_USERNAME": args.username,
        "ADMIN_PASSWORD_HASH": hash_password(args.password),
        "HOST": "127.0.0.1",
        "PORT": str(args.port),
        "URLPATH": path,
        "VITE_URLPATH": path,
        "JWT_SECRET_KEY": f'"{secret_key()}"',
        "SUBSCRIPTION_PATH": sub_path,
    }
    if args.subscription_url_prefix:
        values["SUBSCRIPTION_URL_PREFIX"] = args.subscription_url_prefix.rstrip("/")

    lines = [line for line in parse_env(env_path) if not line.strip().startswith("ADMIN_" + "PASSWORD=")]
    env_path.write_text("\n".join(set_values(lines, values)).rstrip() + "\n", encoding="utf-8")
    os.chmod(env_path, 0o600)
    print(f"Configured {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
