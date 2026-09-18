from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException

from backend.config import config
from backend.db.engine import get_db
from backend.db import crud


router = APIRouter(
    prefix=f"/{config.SUBSCRIPTION_PATH}/push",
    tags=["Subscription Push"],
)

SW_PATH = Path("/opt/ov-panel/frontend/push/pn-sw.js")
VAPID_PUBLIC_PATH = Path("/etc/ov-panel/push/vapid-public.txt")


def _public_origin() -> str:
    prefix = (config.SUBSCRIPTION_URL_PREFIX or "").strip().rstrip("/")
    return prefix or "https://vpn.example.com"


def _subscription_url(user_uuid: str) -> str:
    return f"{_public_origin()}/{config.SUBSCRIPTION_PATH}/{user_uuid}"


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=4096)
    auth: str = Field(min_length=8, max_length=1024)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=8192)
    keys: PushKeys
    timezone: Optional[str] = Field(default=None, max_length=128)
    language: Optional[str] = Field(default=None, max_length=32)
    user_agent: Optional[str] = Field(default=None, max_length=512)


class PushDeleteIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=8192)


class PushTestIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=8192)


def ensure_push_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS web_push_subscriptions (
                endpoint_hash VARCHAR(64) PRIMARY KEY,
                user_uuid VARCHAR(255) NOT NULL,
                endpoint TEXT NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                timezone VARCHAR(128),
                language VARCHAR(32),
                user_agent VARCHAR(512),
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                last_sent_at BIGINT,
                last_slot VARCHAR(64)
            )
            """
        )
    )
    db.commit()


@router.get("/public-key")
async def public_key():
    if not VAPID_PUBLIC_PATH.is_file():
        raise HTTPException(status_code=503, detail="Push key unavailable")

    return {
        "public_key": VAPID_PUBLIC_PATH.read_text(
            encoding="utf-8"
        ).strip()
    }


@router.get("/sw.js")
async def service_worker():
    if not SW_PATH.is_file():
        raise HTTPException(status_code=404)

    return Response(
        content=SW_PATH.read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.post("/subscribe/{uuid}")
async def subscribe(
    uuid: str,
    payload: PushSubscriptionIn,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_uuid(db, uuid)

    if not user:
        raise HTTPException(status_code=404)

    endpoint = payload.endpoint.strip()

    if not endpoint.startswith("https://"):
        raise HTTPException(
            status_code=422,
            detail="Push endpoint must use HTTPS",
        )

    ensure_push_table(db)

    endpoint_hash = hashlib.sha256(
        endpoint.encode("utf-8")
    ).hexdigest()

    now = int(time.time())

    values = {
        "endpoint_hash": endpoint_hash,
        "user_uuid": str(user.uuid),
        "endpoint": endpoint,
        "p256dh": payload.keys.p256dh,
        "auth": payload.keys.auth,
        "timezone": payload.timezone or "UTC",
        "language": payload.language or "fa",
        "user_agent": payload.user_agent or "",
        "now": now,
    }

    existing = db.execute(
        text(
            """
            SELECT endpoint_hash
            FROM web_push_subscriptions
            WHERE endpoint_hash = :endpoint_hash
            """
        ),
        {"endpoint_hash": endpoint_hash},
    ).first()

    if existing:
        db.execute(
            text(
                """
                UPDATE web_push_subscriptions
                SET
                    user_uuid = :user_uuid,
                    endpoint = :endpoint,
                    p256dh = :p256dh,
                    auth = :auth,
                    timezone = :timezone,
                    language = :language,
                    user_agent = :user_agent,
                    enabled = 1,
                    updated_at = :now
                WHERE endpoint_hash = :endpoint_hash
                """
            ),
            values,
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO web_push_subscriptions (
                    endpoint_hash,
                    user_uuid,
                    endpoint,
                    p256dh,
                    auth,
                    timezone,
                    language,
                    user_agent,
                    enabled,
                    created_at,
                    updated_at,
                    last_sent_at,
                    last_slot
                )
                VALUES (
                    :endpoint_hash,
                    :user_uuid,
                    :endpoint,
                    :p256dh,
                    :auth,
                    :timezone,
                    :language,
                    :user_agent,
                    1,
                    :now,
                    :now,
                    NULL,
                    NULL
                )
                """
            ),
            values,
        )

    db.commit()

    return {"success": True, "enabled": True}


@router.delete("/subscribe/{uuid}")
async def unsubscribe(
    uuid: str,
    payload: PushDeleteIn,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_uuid(db, uuid)

    if not user:
        raise HTTPException(status_code=404)

    ensure_push_table(db)

    endpoint_hash = hashlib.sha256(
        payload.endpoint.strip().encode("utf-8")
    ).hexdigest()

    db.execute(
        text(
            """
            DELETE FROM web_push_subscriptions
            WHERE endpoint_hash = :endpoint_hash
              AND user_uuid = :user_uuid
            """
        ),
        {
            "endpoint_hash": endpoint_hash,
            "user_uuid": str(user.uuid),
        },
    )

    db.commit()

    return {"success": True, "enabled": False}



# PN_PUSH_TEST_V643
@router.post("/test/{uuid}")
async def test_push(uuid: str, payload: PushTestIn, db: Session = Depends(get_db)):
    user = crud.get_user_by_uuid(db, uuid)
    if not user:
        raise HTTPException(status_code=404)
    ensure_push_table(db)
    row = db.execute(text("""
        SELECT endpoint_hash, endpoint, p256dh, auth
        FROM web_push_subscriptions
        WHERE user_uuid = :user_uuid AND endpoint = :endpoint AND enabled = 1
        LIMIT 1
    """), {"user_uuid": str(user.uuid), "endpoint": payload.endpoint.strip()}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Active push subscription not found")
    now = int(time.time())
    data = {
        "title": "Private Network · تست نوتیفیکیشن",
        "body": "تست Push واقعی با موفقیت از سرور ارسال شد. برای تمدید یا خرید سرویس به فروشنده خود مراجعه کنید.",
        "icon": "/sub-clients/private-network.webp",
        "badge": "/sub-clients/private-network.webp",
        "tag": f"pn-real-test-{user.uuid}-{now}",
        "timestamp": now * 1000,
        "url": _subscription_url(str(user.uuid)),
    }
    try:
        response = webpush(
            subscription_info={"endpoint": row["endpoint"], "keys": {"p256dh": row["p256dh"], "auth": row["auth"]}},
            data=json.dumps(data, ensure_ascii=False),
            vapid_private_key="/etc/ov-panel/push/vapid-private.pem",
            vapid_claims={"sub": _public_origin()},
            headers={"Urgency": "high"}, ttl=300, timeout=12,
        )
        return {"success": True, "provider_status": int(getattr(response, "status_code", 0) or 0)}
    except WebPushException as exc:
        response=getattr(exc,"response",None)
        code=getattr(response,"status_code",None)
        if code in {404,410}:
            db.execute(text("UPDATE web_push_subscriptions SET enabled=0, updated_at=:now WHERE endpoint_hash=:h"), {"now":now,"h":row["endpoint_hash"]})
            db.commit()
        raise HTTPException(status_code=502, detail=f"Push provider rejected request (HTTP {code or 0})")



# PN_PUSH_TEST_V644
@router.post("/test/{uuid}")
async def test_push(uuid: str, payload: PushTestIn, db: Session = Depends(get_db)):
    user = crud.get_user_by_uuid(db, uuid)
    if not user:
        raise HTTPException(status_code=404)
    ensure_push_table(db)
    row = db.execute(text("""
        SELECT endpoint_hash, endpoint, p256dh, auth, last_test_at
        FROM web_push_subscriptions
        WHERE user_uuid = :user_uuid AND endpoint = :endpoint AND enabled = 1
        LIMIT 1
    """), {"user_uuid": str(user.uuid), "endpoint": payload.endpoint.strip()}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Active push subscription not found")

    now = int(time.time())

    # Anti-spam: a real server test can be sent at most once every 1 hour
    # for this push subscription. Scheduled renewal reminders are separate.
    last_test_at = int(row["last_test_at"] or 0)
    if last_test_at and (now - last_test_at) < (60 * 60):
        remaining = (60 * 60) - (now - last_test_at)
        hours = max(1, (remaining + 3599) // 3600)
        raise HTTPException(
            status_code=429,
            detail=f"تست اعلان برای جلوگیری از اسپم هر ۱ ساعت یک‌بار مجاز است. حدود {hours} ساعت دیگر دوباره تست کنید.",
        )
    data = {
        "title": "Private Network · اعلان سرویس",
        "body": "اعلان‌های سرویس روی این دستگاه فعال است. برای تمدید یا خرید سرویس به فروشنده خود مراجعه کنید.",
        "icon": "/sub-clients/private-network.webp",
        "badge": "/sub-clients/private-network.webp",
        "tag": f"pn-real-test-{user.uuid}-{now}",
        "timestamp": now * 1000,
        "url": _subscription_url(str(user.uuid)),
    }
    try:
        response = webpush(
            subscription_info={"endpoint": row["endpoint"], "keys": {"p256dh": row["p256dh"], "auth": row["auth"]}},
            data=json.dumps(data, ensure_ascii=False),
            vapid_private_key="/etc/ov-panel/push/vapid-private.pem",
            vapid_claims={"sub": _public_origin()},
            headers={"Urgency": "normal"}, ttl=120, timeout=12,
        )

        db.execute(
            text(
                "UPDATE web_push_subscriptions "
                "SET last_test_at=:now, updated_at=:now "
                "WHERE endpoint_hash=:h"
            ),
            {"now": now, "h": row["endpoint_hash"]},
        )
        db.commit()

        return {"success": True, "provider_status": int(getattr(response, "status_code", 0) or 0)}
    except WebPushException as exc:
        response=getattr(exc,"response",None)
        code=getattr(response,"status_code",None)
        if code in {404,410}:
            db.execute(text("UPDATE web_push_subscriptions SET enabled=0, updated_at=:now WHERE endpoint_hash=:h"), {"now":now,"h":row["endpoint_hash"]})
            db.commit()
        raise HTTPException(status_code=502, detail=f"Push provider rejected request (HTTP {code or 0})")


@router.get("/status/{uuid}")
async def push_status(
    uuid: str,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_uuid(db, uuid)

    if not user:
        raise HTTPException(status_code=404)

    ensure_push_table(db)

    count = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM web_push_subscriptions
            WHERE user_uuid = :user_uuid
              AND enabled = 1
            """
        ),
        {"user_uuid": str(user.uuid)},
    ).scalar()

    return {
        "success": True,
        "subscriptions": int(count or 0),
    }
