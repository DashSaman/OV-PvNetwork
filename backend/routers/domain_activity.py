from __future__ import annotations

import ipaddress
import re
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user
from backend.db import crud
from backend.db.engine import get_db
from backend.db.models import DomainActivity, Node
from backend.node.assignment import user_can_access_node
from backend.schema.output import ResponseModel


router = APIRouter(tags=["Domain Activity"])

_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)

_COMMON_SECOND_LEVEL_SUFFIXES = {
    "ac.ir", "ac.uk", "co.id", "co.in", "co.ir", "co.jp", "co.kr",
    "co.nz", "co.uk", "co.za", "com.ar", "com.au", "com.br", "com.cn",
    "com.hk", "com.mx", "com.my", "com.sg", "com.tr", "com.tw", "com.ua",
    "com.vn", "gov.ir", "net.au", "net.ir", "org.au", "org.ir", "org.uk",
}


class DomainActivityEvent(BaseModel):
    common_name: str = Field(min_length=1, max_length=128)
    domain: str = Field(min_length=1, max_length=1024)
    first_seen: int = Field(ge=0)
    last_seen: int = Field(ge=0)
    hit_count: int = Field(ge=1, le=10000)


class DomainActivityBatch(BaseModel):
    events: list[DomainActivityEvent] = Field(
        default_factory=list,
        max_length=1000,
    )


def _normalize_domain(value: str) -> str | None:
    value = (value or "").strip().rstrip(".").lower()

    if not value or len(value) > 1024:
        return None

    try:
        value = value.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return None

    if value.endswith((".local", ".localhost", ".in-addr.arpa", ".ip6.arpa")):
        return None

    try:
        ipaddress.ip_address(value)
        return None
    except ValueError:
        pass

    if not _DOMAIN_PATTERN.fullmatch(value):
        return None

    labels = value.split(".")
    suffix = ".".join(labels[-2:])
    keep = 3 if suffix in _COMMON_SECOND_LEVEL_SUFFIXES else 2

    if len(labels) < keep:
        return None

    # Store only the site-level domain.  Dropping host-specific labels
    # avoids retaining tracking IDs or device names embedded in subdomains.
    return ".".join(labels[-keep:])


def _node_from_key(db: Session, node_key: str) -> Node:
    node_key = (node_key or "").strip()

    if not node_key:
        raise HTTPException(status_code=401, detail="Missing node key")

    node = (
        db.query(Node)
        .filter(
            Node.key == node_key,
            Node.status.is_(True),
        )
        .first()
    )

    if node is None:
        raise HTTPException(status_code=401, detail="Invalid node key")

    return node


def _user_for_common_name(db: Session, node: Node, common_name: str):
    suffix = f"-{node.name}"

    if not common_name.endswith(suffix):
        return None

    username = common_name[: -len(suffix)]

    if not username:
        return None

    user = crud.get_user_by_name(db, username)

    if user is None:
        return None

    if not user_can_access_node(db, user.uuid, node.id):
        return None

    return user


@router.post("/integrations/mirza/domain-activity")
async def ingest_domain_activity(
    request: DomainActivityBatch,
    db: Session = Depends(get_db),
    node_key: str = Header(..., alias="X-OV-Node-Key"),
):
    node = _node_from_key(db, node_key)

    if not request.events:
        return {
            "success": True,
            "accepted_domains": 0,
            "accepted_hits": 0,
            "ignored": 0,
        }

    now = int(time.time())
    users_by_common_name = {}
    merged: dict[tuple[str, int, str], dict] = {}
    ignored = 0

    for event in request.events:
        domain = _normalize_domain(event.domain)

        if domain is None:
            ignored += 1
            continue

        if event.common_name not in users_by_common_name:
            users_by_common_name[event.common_name] = _user_for_common_name(
                db,
                node,
                event.common_name,
            )

        user = users_by_common_name[event.common_name]

        if user is None:
            ignored += 1
            continue

        # Collector batches are short-lived.  Clamp obviously skewed node
        # clocks instead of allowing future timestamps into the history.
        last_seen = int(event.last_seen)

        if last_seen < now - 86400 or last_seen > now + 300:
            last_seen = now

        first_seen = min(int(event.first_seen), last_seen)
        first_seen = max(first_seen, last_seen - 86400)

        identity = (str(user.uuid), int(node.id), domain)
        current = merged.get(identity)

        if current is None:
            merged[identity] = {
                "user_uuid": str(user.uuid),
                "node_id": int(node.id),
                "domain": domain,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "hit_count": int(event.hit_count),
            }
            continue

        current["first_seen"] = min(current["first_seen"], first_seen)
        current["last_seen"] = max(current["last_seen"], last_seen)
        current["hit_count"] = min(
            100000,
            current["hit_count"] + int(event.hit_count),
        )

    rows = list(merged.values())

    if rows:
        statement = pg_insert(DomainActivity).values(rows)
        excluded = statement.excluded

        statement = statement.on_conflict_do_update(
            constraint="uq_domain_activity_user_node_domain",
            set_={
                "first_seen": func.least(
                    DomainActivity.first_seen,
                    excluded.first_seen,
                ),
                "last_seen": func.greatest(
                    DomainActivity.last_seen,
                    excluded.last_seen,
                ),
                "hit_count": DomainActivity.hit_count + excluded.hit_count,
            },
        )

        try:
            db.execute(statement)
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {
        "success": True,
        "accepted_domains": len(rows),
        "accepted_hits": sum(row["hit_count"] for row in rows),
        "ignored": ignored,
    }


@router.get(
    "/users/{user_uuid}/domain-activity",
    response_model=ResponseModel,
)
async def get_user_domain_activity(
    user_uuid: str,
    search: str = Query(default="", max_length=100),
    days: int = Query(default=7, ge=1, le=90),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    if actor.get("type") != "main_admin":
        raise HTTPException(
            status_code=403,
            detail="Main administrator required",
        )

    user = crud.get_user_by_uuid(db, user_uuid)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    cutoff = int(time.time()) - (int(days) * 86400)

    query = (
        db.query(
            DomainActivity,
            Node.name.label("node_name"),
        )
        .join(Node, Node.id == DomainActivity.node_id)
        .filter(
            DomainActivity.user_uuid == user_uuid,
            DomainActivity.last_seen >= cutoff,
        )
    )

    search = (search or "").strip().lower()

    if search:
        escaped = (
            search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        query = query.filter(
            DomainActivity.domain.ilike(
                f"%{escaped}%",
                escape="\\",
            )
        )

    total = query.count()
    summary = query.with_entities(
        func.coalesce(func.sum(DomainActivity.hit_count), 0),
    ).scalar()

    rows = (
        query.order_by(
            DomainActivity.last_seen.desc(),
            DomainActivity.domain.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        {
            "domain": activity.domain,
            "node_id": activity.node_id,
            "node_name": node_name,
            "first_seen": int(activity.first_seen),
            "last_seen": int(activity.last_seen),
            "hit_count": int(activity.hit_count),
        }
        for activity, node_name in rows
    ]

    return ResponseModel(
        success=True,
        msg="DNS domain activity retrieved",
        data={
            "user_uuid": str(user.uuid),
            "username": user.name,
            "days": int(days),
            "search": search,
            "page": int(page),
            "page_size": int(page_size),
            "total": int(total),
            "total_hits": int(summary or 0),
            "items": items,
            "limitations": (
                "DNS observations only; encrypted DNS, caching, and "
                "prefetching can make this list incomplete or include "
                "domains that were not opened directly. URLs and HTTPS "
                "content are not recorded."
            ),
        },
    )
