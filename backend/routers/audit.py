from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth.auth import get_current_user
from backend.db.engine import get_db
from backend.db.models import AuditLog
from backend.schema.output import ResponseModel

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/", response_model=ResponseModel)
async def list_audit_logs(
    actor: str | None = None,
    action: str | None = None,
    resource: str | None = None,
    success: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user["type"] != "main_admin":
        raise HTTPException(
            status_code=403,
            detail="Main administrator required",
        )

    query = db.query(AuditLog)

    if actor:
        query = query.filter(AuditLog.actor == actor)

    if action:
        query = query.filter(AuditLog.action == action.upper())

    if resource:
        query = query.filter(AuditLog.resource.ilike(f"%{resource}%"))

    if success is not None:
        query = query.filter(AuditLog.success == success)

    total = query.count()

    rows = (
        query.order_by(AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": row.id,
            "actor": row.actor,
            "actor_type": row.actor_type,
            "action": row.action,
            "resource": row.resource,
            "status_code": row.status_code,
            "success": row.success,
            "ip_address": row.ip_address,
            "user_agent": row.user_agent,
            "request_id": row.request_id,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at,
        }
        for row in rows
    ]

    return ResponseModel(
        success=True,
        msg="Audit logs retrieved",
        data={
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    )
