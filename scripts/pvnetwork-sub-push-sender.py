#!/opt/pvnetwork-panel/.venv/bin/python3

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from pywebpush import webpush, WebPushException
from sqlalchemy import text

from backend.config import config
from backend.db.engine import SessionLocal
from backend.db.models import User


PRIVATE_KEY = "/etc/pvnetwork-panel/push/vapid-private.pem"

BASE_URL = os.environ.get(
    "PUSH_BASE_URL",
    config.SUBSCRIPTION_URL_PREFIX or "https://example.invalid",
).rstrip("/")

# 10:00 and 20:00 local device time = 10 hours apart.
SEND_HOURS = (10, 20)

# Do not keep an old queued push until the next notification.
PUSH_TTL_SECONDS = 8 * 60 * 60
LOW_TRAFFIC_THRESHOLD_BYTES = 1 * 1024 * 1024 * 1024


def safe_zone(name):
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def reminder_text(days, low_traffic, remaining_bytes):
    parts = []
    if 0 <= days <= 5:
        if days == 0:
            parts.append("امروز آخرین روز اشتراک شماست.")
        elif days == 1:
            parts.append("فقط ۱ روز تا پایان اشتراک شما باقی مانده.")
        else:
            parts.append(f"فقط {days} روز تا پایان اشتراک شما باقی مانده.")
    if low_traffic:
        gb = max(0, remaining_bytes) / (1024 ** 3)
        parts.append(f"حجم باقی‌مانده شما {gb:.2f} گیگابایت است.")
    parts.append("برای تمدید یا خرید سرویس به فروشنده خود مراجعه کنید.")
    return " ".join(parts)


def update_sent(db, endpoint_hash, slot):
    now = int(time.time())

    db.execute(
        text(
            """
            UPDATE web_push_subscriptions
            SET
                last_sent_at = :now,
                last_slot = :slot,
                updated_at = :now
            WHERE endpoint_hash = :endpoint_hash
            """
        ),
        {
            "now": now,
            "slot": slot,
            "endpoint_hash": endpoint_hash,
        },
    )

    db.commit()


def disable_stale(db, endpoint_hash):
    db.execute(
        text(
            """
            UPDATE web_push_subscriptions
            SET enabled = 0, updated_at = :now
            WHERE endpoint_hash = :endpoint_hash
            """
        ),
        {
            "now": int(time.time()),
            "endpoint_hash": endpoint_hash,
        },
    )

    db.commit()


def main():
    db = SessionLocal()

    checked = 0
    sent = 0
    skipped = 0
    stale = 0
    failed = 0

    try:
        rows = db.execute(
            text(
                """
                SELECT
                    endpoint_hash,
                    user_uuid,
                    endpoint,
                    p256dh,
                    auth,
                    timezone,
                    last_slot
                FROM web_push_subscriptions
                WHERE enabled = 1
                ORDER BY user_uuid, endpoint_hash
                """
            )
        ).mappings().all()

        for row in rows:
            checked += 1

            user = (
                db.query(User)
                .filter(User.uuid == row["user_uuid"])
                .first()
            )

            if not user or not bool(user.is_active):
                skipped += 1
                continue

            local_now = datetime.now(
                safe_zone(row["timezone"])
            )

            if local_now.hour not in SEND_HOURS:
                skipped += 1
                continue

            days = (
                user.expiry_date - local_now.date()
            ).days

            total_bytes = int(getattr(user, "total", 0) or 0)
            used_bytes = int(getattr(user, "used", 0) or 0)
            finite_volume = total_bytes > 0
            remaining_bytes = max(0, total_bytes - used_bytes) if finite_volume else 0

            expiry_due = 0 <= days <= 5
            low_traffic_due = finite_volume and remaining_bytes <= LOW_TRAFFIC_THRESHOLD_BYTES

            if not (expiry_due or low_traffic_due):
                skipped += 1
                continue

            slot = (
                f"{local_now.date().isoformat()}"
                f"@{local_now.hour:02d}"
            )

            if row["last_slot"] == slot:
                skipped += 1
                continue

            payload = {
                "title": "Private Network · یادآوری تمدید",
                "body": reminder_text(days, low_traffic_due, remaining_bytes),
                "icon": "/sub-clients/private-network.webp",
                "badge": "/sub-clients/private-network.webp",
                "tag": (
                    "pn-renewal-"
                    + str(row["user_uuid"])
                    + "-"
                    + slot.replace("@", "-")
                ),
                "timestamp": int(time.time() * 1000),
                "url": (
                    f"{BASE_URL}/"
                    f"{config.SUBSCRIPTION_PATH}/"
                    f"{row['user_uuid']}"
                ),
            }

            try:
                webpush(
                    subscription_info={
                        "endpoint": row["endpoint"],
                        "keys": {
                            "p256dh": row["p256dh"],
                            "auth": row["auth"],
                        },
                    },
                    data=json.dumps(
                        payload,
                        ensure_ascii=False,
                    ),
                    vapid_private_key=PRIVATE_KEY,
                    vapid_claims={
                        "sub": BASE_URL,
                    },
                    ttl=PUSH_TTL_SECONDS,
                    timeout=12,
                )

                update_sent(
                    db,
                    row["endpoint_hash"],
                    slot,
                )

                sent += 1

                print(
                    "PUSH_SENT "
                    f"user={row['user_uuid']} "
                    f"slot={slot} "
                    f"days={days}",
                    flush=True,
                )

            except WebPushException as exc:
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)

                if status_code in {404, 410}:
                    disable_stale(db, row["endpoint_hash"])
                    stale += 1
                else:
                    failed += 1

                print(
                    "PUSH_FAILED "
                    f"user={row['user_uuid']} "
                    f"http={status_code or 0}",
                    flush=True,
                )

            except Exception as exc:
                failed += 1

                print(
                    "PUSH_FAILED "
                    f"user={row['user_uuid']} "
                    f"error={type(exc).__name__}:"
                    f"{str(exc)[:120]}",
                    flush=True,
                )

        print(
            "PUSH_RUN_DONE "
            f"checked={checked} "
            f"sent={sent} "
            f"skipped={skipped} "
            f"stale={stale} "
            f"failed={failed}",
            flush=True,
        )

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
