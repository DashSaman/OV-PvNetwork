#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import sys
import urllib.error
import urllib.parse
import urllib.request

EXPECTED = {
    "/healthz": 200,
    "/openapi.json": 404,
    "/redoc": 404,
    "/api/users/": 401,
    "/api/security/": 401,
}
UNTRUSTED_ORIGIN = "https://security-probe.invalid"


class ProbeFailure(RuntimeError):
    pass


def validate_base_url(value: str, allow_http_loopback: bool = False) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if not parsed.hostname or parsed.username or parsed.password:
        raise ProbeFailure("base URL must be an origin without credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ProbeFailure("base URL must not include a path, query, or fragment")
    if parsed.scheme == "https":
        pass
    elif parsed.scheme == "http" and allow_http_loopback:
        host = parsed.hostname
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host == "localhost"
        if not loopback:
            raise ProbeFailure("HTTP override is limited to loopback")
    else:
        raise ProbeFailure("HTTPS is required")
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}"


def _lower_headers(headers) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def check_no_cors_grant(headers, origin: str) -> None:
    granted = _lower_headers(headers).get("access-control-allow-origin", "")
    if granted in {origin, "*"}:
        raise ProbeFailure(f"untrusted CORS origin granted: {granted}")


def check_security_headers(headers) -> None:
    values = _lower_headers(headers)
    required = (
        "strict-transport-security",
        "content-security-policy",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "permissions-policy",
    )
    missing = [name for name in required if not values.get(name)]
    if missing:
        raise ProbeFailure("missing security headers: " + ",".join(missing))
    if values["x-content-type-options"].lower() != "nosniff":
        raise ProbeFailure("X-Content-Type-Options must be nosniff")
    if values["x-frame-options"].upper() != "DENY":
        raise ProbeFailure("X-Frame-Options must be DENY")


def _fetch(request, opener, timeout: float):
    try:
        with opener(request, timeout=timeout) as response:
            response.read(1)
            return int(response.status), response.headers
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.headers


def run_probe(base_url: str, *, opener=urllib.request.urlopen, allow_http_loopback: bool = False) -> list[str]:
    origin = validate_base_url(base_url, allow_http_loopback=allow_http_loopback)
    lines: list[str] = []
    for path, expected in EXPECTED.items():
        request = urllib.request.Request(
            origin + path,
            headers={
                "Origin": UNTRUSTED_ORIGIN,
                "User-Agent": "PVNetwork-Security-Probe/1",
            },
            method="GET",
        )
        status, headers = _fetch(request, opener, timeout=10.0)
        if status != expected:
            raise ProbeFailure(f"{path} expected {expected}, got {status}")
        check_no_cors_grant(headers, UNTRUSTED_ORIGIN)
        if path == "/healthz":
            check_security_headers(headers)
        lines.append(f"CHECK path={path} status={status} PASS")
    lines.append("PVNETWORK_SECURITY_READONLY_PROBE=PASS")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PVNetwork credential-free security release probe")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--allow-http-loopback", action="store_true")
    args = parser.parse_args(argv)
    try:
        lines = run_probe(args.base_url, allow_http_loopback=args.allow_http_loopback)
    except ProbeFailure as exc:
        print(f"PVNETWORK_SECURITY_READONLY_PROBE=FAIL detail={exc}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
