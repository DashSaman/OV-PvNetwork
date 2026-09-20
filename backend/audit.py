import hashlib
import time
import uuid

import jwt
from jwt import InvalidTokenError as JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from backend.auth.auth import ALGORITHM
from backend.config import config
from backend.db.engine import SessionLocal
from backend.db.models import ApiToken, AuditLog


def _resolve_actor(authorization: str) -> tuple[str, str]:
    if not authorization.lower().startswith("bearer "):
        return "anonymous", "anonymous"

    raw = authorization.split(" ", 1)[1].strip()

    if raw.startswith(("pvn_", "ovp_")):
        digest = hashlib.sha256(raw.encode()).hexdigest()
        db = SessionLocal()
        try:
            token = (
                db.query(ApiToken)
                .filter(
                    ApiToken.token_hash == digest,
                    ApiToken.revoked_at.is_(None),
                )
                .first()
            )
            if token:
                return str(token.created_by)[:128], "api_token"
            return "invalid-token", "api_token"
        finally:
            db.close()

    try:
        payload = jwt.decode(
            raw,
            config.JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        actor = str(payload.get("sub") or "unknown")[:128]
        actor_type = str(payload.get("type") or "unknown")[:32]
        return actor, actor_type
    except JWTError:
        return "invalid-token", "unknown"


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.monotonic()
        supplied_request_id = request.headers.get("x-request-id", "").strip()
        request_id = (supplied_request_id or uuid.uuid4().hex)[:64]
        status = 500

        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            if (
                request.method in {"POST", "PUT", "PATCH", "DELETE"}
                and request.url.path.startswith("/api")
            ):
                authorization = request.headers.get("authorization", "")
                actor, actor_type = _resolve_actor(authorization)

                forwarded = request.headers.get("x-forwarded-for", "")
                ip = (
                    forwarded.split(",", 1)[0].strip()
                    if forwarded
                    else (request.client.host if request.client else None)
                )

                db = SessionLocal()
                try:
                    db.add(
                        AuditLog(
                            actor=actor,
                            actor_type=actor_type,
                            action=request.method,
                            resource=request.url.path[:512],
                            status_code=status,
                            success=200 <= status < 400,
                            ip_address=(ip or "")[:64] or None,
                            user_agent=request.headers.get(
                                "user-agent", ""
                            )[:512] or None,
                            request_id=request_id,
                            duration_ms=int(
                                (time.monotonic() - start) * 1000
                            ),
                            created_at=int(time.time()),
                        )
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                finally:
                    db.close()
