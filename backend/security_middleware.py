import ipaddress
import json
import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.config import config
from backend.db.engine import SessionLocal
from backend.db.models import SecuritySettings

_hits = defaultdict(deque)
_login_hits = defaultdict(deque)
_cache = {"at": 0, "v": None}
LOGIN_RATE_LIMIT_PER_MINUTE = max(3, int(config.LOGIN_RATE_LIMIT_PER_MINUTE))
EXEMPT_PREFIXES = (
    "/api/integrations/mirza/",
    "/api/nodes/public-health/",
)


def cfg():
    now = time.time()
    if _cache["v"] and now - _cache["at"] < 10:
        return _cache["v"]
    db = SessionLocal()
    try:
        row = db.query(SecuritySettings).filter(SecuritySettings.id == 1).first()
        value = {
            "rate": bool(row and row.rate_limit_enabled),
            "limit": int(row.rate_limit_per_minute if row else 120),
            "allow": bool(row and row.ip_allowlist_enabled),
            "cidrs": json.loads(row.allowed_cidrs if row else "[]"),
        }
    finally:
        db.close()
    _cache.update(at=now, v=value)
    return value


def client_ip(request) -> str:
    peer = request.client.host if request.client else ""
    forwarded = request.headers.get("x-forwarded-for", "")
    # The panel binds to loopback in Production. Nginx appends remote_addr to
    # X-Forwarded-For, so the LAST element cannot be replaced by a client-
    # supplied leading value. Direct non-loopback requests ignore XFF.
    candidate = peer
    if peer in {"127.0.0.1", "::1"} and forwarded:
        candidate = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return peer or "unknown"


def _limited(bucket_map, key: str, limit: int, now: float) -> bool:
    bucket = bucket_map[key]
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    # Bound memory from expired one-shot source addresses.
    if len(bucket_map) > 8192:
        for old_key in list(bucket_map)[:1024]:
            q = bucket_map.get(old_key)
            if q is not None and (not q or q[-1] < now - 60):
                bucket_map.pop(old_key, None)
    return False


BASE_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; font-src 'self' data:; "
    "connect-src 'self' https: wss:; object-src 'none'; base-uri 'self'; "
    "frame-ancestors 'none'; form-action 'self'"
)

# PVN-1009: the public subscription page (/sub) is a single Jinja template whose
# runtime has always been inline scripts; the strict CSP shipped in v1.0.8
# silently disabled them (language/theme switching, renewal countdown, copy
# buttons). Until the template migrates to a nonce/external-file architecture
# (registered as the follow-up task), this page gets 'unsafe-inline' for
# scripts only. Jinja autoescaping keeps reflected values inert.
SUBSCRIPTION_INLINE_CSP = BASE_CSP.replace(
    "script-src 'self'", "script-src 'self' 'unsafe-inline'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        path = request.url.path
        sub_prefix = f"/{os.getenv('SUBSCRIPTION_PATH', 'sub').strip('/')}"
        if path == sub_prefix or path.startswith(f"{sub_prefix}/"):
            headers.setdefault("Content-Security-Policy", SUBSCRIPTION_INLINE_CSP)
        else:
            headers.setdefault("Content-Security-Policy", BASE_CSP)
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        if request.method in {"OPTIONS", "HEAD"} or request.url.path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        ip = client_ip(request)
        now = time.time()
        if request.url.path == "/api/login" and _limited(
            _login_hits, ip, LOGIN_RATE_LIMIT_PER_MINUTE, now
        ):
            return JSONResponse(
                {"detail": "Too many login attempts"},
                429,
                headers={"Retry-After": "60"},
            )

        conf = cfg()
        if conf["allow"] and request.url.path != "/api/login":
            try:
                allowed = any(
                    ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
                    for cidr in conf["cidrs"]
                )
            except Exception:
                allowed = False
            if not allowed:
                return JSONResponse({"detail": "IP is not allowed"}, 403)

        if conf["rate"] and _limited(_hits, ip, conf["limit"], now):
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                429,
                headers={"Retry-After": "60"},
            )
        return await call_next(request)




def api_scope_area(path: str) -> str:
    if (
        path == "/api/users" or path.startswith("/api/users/")
        or path.startswith("/api/anyconnect/users/")
        or path.startswith("/api/router-openvpn/users/")
    ):
        return "users"
    if path.startswith("/api/operations/users/"):
        if path == "/api/operations/users/transfer":
            return "nodes"
        return "users"
    if (
        path == "/api/nodes" or path.startswith("/api/nodes/")
        or path == "/api/fleet" or path.startswith("/api/fleet/")
        or path.startswith("/api/router-openvpn/nodes/")
        or path == "/api/operations/rebalance"
    ):
        return "nodes"
    if (
        path == "/api/audit" or path.startswith("/api/audit/")
        or path == "/api/operations/audit"
    ):
        return "audit"
    return "settings"

class ApiScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith(("bearer pvn_", "bearer ovp_")):
            return await call_next(request)
        import hashlib
        import time as _time
        from backend.db.models import ApiToken

        raw = auth.split(" ", 1)[1]
        db = SessionLocal()
        try:
            row = db.query(ApiToken).filter(
                ApiToken.token_hash == hashlib.sha256(raw.encode()).hexdigest(),
                ApiToken.revoked_at.is_(None),
            ).first()
            if not row or (row.expires_at and row.expires_at <= int(_time.time())):
                return JSONResponse({"detail": "Invalid API token"}, 401)
            scopes = set(json.loads(row.scopes))
            path = request.url.path
            write = request.method not in {"GET", "HEAD", "OPTIONS"}
            area = api_scope_area(path)
            required = f'{area}:{"write" if write else "read"}'
            if required not in scopes:
                return JSONResponse({"detail": f"Missing scope: {required}"}, 403)
        finally:
            db.close()
        return await call_next(request)
