"""Local-only DNS activity bridge from the node collector to PVNetwork Panel."""

import json
import urllib.error
from core.controller_transport import open_controller,require_local_hook
import urllib.request
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.config import settings


router = APIRouter(tags=["domain_activity"])

_PANEL_URL = settings.panel_url.rstrip('/') + '/api/integrations/mirza/domain-activity'


def _forward(events: list[dict]):
    if not settings.panel_url:
        return JSONResponse(status_code=503,content={'success':False,'detail':'Controller callback is not configured'})
    body = json.dumps(
        {"events": events},
        separators=(",", ":"),
    ).encode("utf-8")

    request = urllib.request.Request(
        _PANEL_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-PVNetwork-Node-Key": settings.api_key,
        },
    )

    try:
        with open_controller(request, timeout=8) as response:
            status_code = response.status
            raw = response.read().decode("utf-8", errors="replace")

    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw = exc.read().decode("utf-8", errors="replace")

    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "detail": "Central domain collector is unavailable",
                "error": type(exc).__name__,
            },
        )

    try:
        content = json.loads(raw) if raw else {}
    except Exception:
        content = {"raw": raw[:500]}

    return JSONResponse(
        status_code=status_code,
        content=content,
    )


@router.post("/local-domain-activity")
async def local_domain_activity(payload: dict, request: Request):
    require_local_hook(request)
    client_host = request.client.host if request.client else ""

    if client_host not in {"127.0.0.1", "::1"}:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "detail": "Local access only",
            },
        )

    raw_events = payload.get("events")

    if not isinstance(raw_events, list) or len(raw_events) > 1000:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "detail": "Invalid domain activity batch",
            },
        )

    events = []

    for item in raw_events:
        if not isinstance(item, dict):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "detail": "Invalid domain activity event",
                },
            )

        common_name = str(item.get("common_name", "")).strip()
        domain = str(item.get("domain", "")).strip()

        try:
            first_seen = int(item.get("first_seen"))
            last_seen = int(item.get("last_seen"))
            hit_count = int(item.get("hit_count"))
        except (TypeError, ValueError):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "detail": "Invalid domain activity event",
                },
            )

        if (
            not common_name
            or len(common_name) > 128
            or not domain
            or len(domain) > 1024
            or first_seen < 0
            or last_seen < first_seen
            or hit_count < 1
            or hit_count > 10000
        ):
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "detail": "Invalid domain activity event",
                },
            )

        events.append(
            {
                "common_name": common_name,
                "domain": domain,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "hit_count": hit_count,
            }
        )

    return _forward(events)
