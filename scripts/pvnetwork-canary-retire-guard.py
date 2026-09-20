#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

_PROXY_RE = re.compile(r"^\s*proxy_pass\s+http://127\.0\.0\.1:(\d+)\s*;", re.MULTILINE)


def validate_proxy_targets(site_text: str, canonical_port: int, canary_port: int) -> list[int]:
    active_lines = "\n".join(
        line for line in site_text.splitlines() if not line.lstrip().startswith("#")
    )
    targets = [int(value) for value in _PROXY_RE.findall(active_lines)]
    if canary_port in targets:
        raise RuntimeError(f"canary upstream {canary_port} is still active in nginx site")
    if canonical_port not in targets:
        raise RuntimeError(f"canonical upstream {canonical_port} is missing from nginx site")
    return targets


def http_status(url: str, timeout: float = 5.0) -> int:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except OSError:
        return 0


def require_nginx_syntax_ok(run=subprocess.run) -> None:
    result = run(
        ["nginx", "-t"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if int(result.returncode) != 0:
        raise RuntimeError("nginx syntax check failed")


def reload_nginx_service(run=subprocess.run) -> None:
    result = run(
        ["systemctl", "reload", "nginx"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if int(result.returncode) != 0:
        raise RuntimeError("nginx reload failed")


def guard_retirement(
    site_text: str,
    *,
    canonical_port: int,
    canary_port: int,
    canonical_url: str,
    public_url: str,
    http_status=http_status,
) -> list[int]:
    targets = validate_proxy_targets(site_text, canonical_port, canary_port)
    canonical_status = int(http_status(canonical_url) or 0)
    if canonical_status != 200:
        raise RuntimeError(f"canonical health returned {canonical_status:03d}")
    public_status = int(http_status(public_url) or 0)
    if public_status != 200:
        raise RuntimeError(f"public health returned {public_status:03d}")
    return targets


def main(argv=None, *, syntax_check=require_nginx_syntax_ok, reload_nginx=reload_nginx_service, http_get=http_status) -> int:
    parser = argparse.ArgumentParser(description="Verify canonical panel traffic before retiring the canary")
    parser.add_argument("--nginx-site", required=True)
    parser.add_argument("--canonical-port", type=int, default=19001)
    parser.add_argument("--canary-port", type=int, default=19002)
    parser.add_argument("--canonical-url")
    parser.add_argument("--public-url", required=True)
    args = parser.parse_args(argv)
    canonical_url = args.canonical_url or f"http://127.0.0.1:{args.canonical_port}/healthz"
    try:
        syntax_check()
        site_text = Path(args.nginx_site).read_text(encoding="utf-8")
        validate_proxy_targets(site_text, args.canonical_port, args.canary_port)
        reload_nginx()
        targets = guard_retirement(
            site_text,
            canonical_port=args.canonical_port,
            canary_port=args.canary_port,
            canonical_url=canonical_url,
            public_url=args.public_url,
            http_status=http_get,
        )
    except Exception as exc:
        print("CANARY_RETIRE_SAFE=NO")
        print(f"REASON={str(exc)[:240]}")
        return 1
    print("CANARY_RETIRE_SAFE=YES")
    print("ACTIVE_PROXY_PORTS=" + ",".join(str(port) for port in targets))
    print(f"CANONICAL_HTTP=200")
    print(f"PUBLIC_HTTP=200")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
