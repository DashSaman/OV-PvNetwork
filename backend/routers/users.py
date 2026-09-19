from calendar import monthrange
from datetime import date, datetime, timedelta
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.operations.daily_checks import enforce_user_limits, reset_shared_user_usage
from backend.schema.output import ResponseModel, Users
from backend.schema._input import CreateUser, RenewUser, UpdateUser, UserNodeAssignmentUpdate
from backend.db.engine import get_db
from backend.db.models import (
    ActiveSession,
    Admin,
    AnyConnectCredential,
    ResellerCreditTransaction,
    User,
    UserNode,
    Node,
)
from backend.routers.anyconnect import provision_new_user_if_enabled
from backend.operations.user_renewal import build_renewal_plan, unlimited_reset_expiry
from backend.node.assignment import (
    change_user_status_on_assigned_nodes,
    replace_user_node_assignments,
)
from backend.db import crud
from backend.auth.auth import get_current_user
from backend.node.task import delete_user_on_all_nodes

router = APIRouter(prefix="/users", tags=["Users"])


# A session is considered online only while its heartbeat is fresh.
# Current OpenVPN heartbeat runs approximately every 20 seconds.
_USER_ONLINE_TTL = 90


def _owned_user_or_404(db: Session, uuid: str, actor: dict):
    target = crud.get_user_by_uuid(db, uuid)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if actor["type"] == "admin" and target.owner != actor["username"]:
        # Do not reveal whether another reseller's UUID exists.
        raise HTTPException(status_code=404, detail="User not found")
    return target


def _finite_total(value):
    return int(value or 0)


def _add_calendar_months(start: date, months: int) -> date:
    # OV_RESELLER_EXPIRY_MONTHS_LOCK_V1
    months = int(months)
    if months < 1 or months > 120:
        raise HTTPException(
            status_code=400,
            detail="Reseller duration must be between 1 and 120 months",
        )
    month_index = (start.month - 1) + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def _change_reseller_entitlements(
    db: Session, username: str, *, traffic_delta: int = 0,
    unlimited_delta: int = 0, action: str, user_uuid=None, note=None,
):
    # OV_RESELLER_UNLIMITED_SLOTS_V2
    admin = db.query(Admin).filter(Admin.username == username).with_for_update().first()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=403, detail="Reseller account is disabled")

    new_used = int(admin.quota_used or 0) + int(traffic_delta)
    new_unlimited_used = int(admin.unlimited_quota_used or 0) + int(unlimited_delta)
    if new_used < 0 or new_unlimited_used < 0:
        raise HTTPException(status_code=409, detail="Invalid reseller entitlement state")
    if new_used > int(admin.quota_total or 0):
        remaining = int(admin.quota_total or 0) - int(admin.quota_used or 0)
        raise HTTPException(status_code=409, detail=f"Insufficient reseller credit. Remaining bytes: {remaining}")
    if new_unlimited_used > int(admin.unlimited_quota_total or 0):
        remaining = int(admin.unlimited_quota_total or 0) - int(admin.unlimited_quota_used or 0)
        raise HTTPException(status_code=409, detail=f"Insufficient unlimited account quota. Remaining accounts: {remaining}")

    admin.quota_used = new_used
    admin.unlimited_quota_used = new_unlimited_used

    if int(traffic_delta) != 0:
        db.add(ResellerCreditTransaction(
            admin_id=admin.id, amount=int(traffic_delta), balance_after=new_used,
            action=action, user_uuid=user_uuid, note=note, created_at=int(time.time()),
        ))
    if int(unlimited_delta) != 0:
        unlimited_note = f"unlimited_delta={int(unlimited_delta)}; unlimited_balance_after={new_unlimited_used}"
        if note:
            unlimited_note = f"{note}; {unlimited_note}"
        db.add(ResellerCreditTransaction(
            admin_id=admin.id, amount=0, balance_after=new_used,
            action=f"{action}_unlimited", user_uuid=user_uuid,
            note=unlimited_note, created_at=int(time.time()),
        ))
    return admin

def _users_with_live_state(
    db: Session,
    users,
):
    """
    Attach live VPN connection state using ONE grouped DB query.

    No per-user query is performed, so this remains efficient
    with hundreds or thousands of users.
    """

    cutoff = int(time.time()) - _USER_ONLINE_TTL

    rows = (
        db.query(
            ActiveSession.user_uuid,
            func.count(
                ActiveSession.session_id
            ).label("online_count"),
        )
        .filter(
            ActiveSession.last_seen >= cutoff
        )
        .group_by(
            ActiveSession.user_uuid
        )
        .all()
    )

    counts = {
        str(user_uuid): int(count)
        for user_uuid, count in rows
    }

    user_uuids = [str(item.uuid) for item in users if item.uuid]
    assignment_rows = []
    if user_uuids:
        assignment_rows = (
            db.query(UserNode.user_uuid, UserNode.node_id)
            .filter(UserNode.user_uuid.in_(user_uuids))
            .all()
        )
    assignments: dict[str, list[int]] = {}
    for user_uuid, node_id in assignment_rows:
        assignments.setdefault(str(user_uuid), []).append(int(node_id))
    # Legacy users without explicit user_nodes rows retain historical all-node
    # access; expose their effective assignment instead of an empty list.
    all_node_ids = [int(row[0]) for row in db.query(Node.id).order_by(Node.id).all()]

    credential_rows = []
    if user_uuids:
        credential_rows = (
            db.query(
                AnyConnectCredential.user_uuid,
                AnyConnectCredential.enabled,
                AnyConnectCredential.password_ciphertext,
            )
            .filter(AnyConnectCredential.user_uuid.in_(user_uuids))
            .all()
        )

    credentials = {
        str(user_uuid): {
            "enabled": bool(enabled),
            "password_available": bool(password_ciphertext),
        }
        for user_uuid, enabled, password_ciphertext in credential_rows
    }

    output = []

    for item in users:

        online_count = counts.get(
            str(item.uuid),
            0,
        )

        #
        # Transient response-only fields.
        # Nothing extra is written to users table.
        #
        item.online_count = online_count
        item.is_online = online_count > 0

        credential = credentials.get(str(item.uuid))
        item.anyconnect_configured = credential is not None
        item.anyconnect_enabled = bool(
            credential and credential["enabled"]
        )
        item.anyconnect_password_available = bool(
            credential and credential["password_available"]
        )
        item.node_ids = sorted(assignments.get(str(item.uuid), all_node_ids))

        output.append(
            Users.from_orm(item)
        )

    return output



@router.get("/", response_model=ResponseModel)
async def get_all_users(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    if user["type"] == "main_admin":
        all_users = crud.get_all_users(db)
        users_list = _users_with_live_state(db, all_users)
        return ResponseModel(
            success=True,
            msg="Users retrieved successfully",
            data=users_list,
        )

    elif user["type"] == "admin":
        admin_users = crud.get_users_by_admin(db, admin_username=user["username"])
        users_list = _users_with_live_state(db, admin_users)
        return ResponseModel(
            success=True,
            msg="Users retrieved successfully",
            data=users_list,
        )

    return ResponseModel(
        success=False,
        msg="Unauthorized access",
    )


@router.get("/{uuid}", response_model=ResponseModel)
async def reset_user_usage(uuid: str, db: Session = Depends(get_db), actor: dict = Depends(get_current_user)):
    # MULTINODE_RESET_ROUTE_V2
    # Unlimited accounts use Reset Usage as the start of a fresh 30-day cycle.
    # Finite accounts keep their existing expiry date.
    target_user = _owned_user_or_404(db, uuid, actor)
    renewed_expiry = unlimited_reset_expiry(
        total=_finite_total(target_user.total),
        today=date.today(),
    )

    await reset_shared_user_usage(
        target_user,
        db,
    )

    node_sync = None
    if renewed_expiry is not None:
        target_user.expiry_date = renewed_expiry
        target_user.is_active = True
        db.commit()
        db.refresh(target_user)
        node_sync = await change_user_status_on_assigned_nodes(
            target_user.uuid,
            target_user.name,
            True,
            db,
        )

    return ResponseModel(
        success=True,
        msg=(
            "Unlimited user usage reset and renewed for 30 days"
            if renewed_expiry is not None
            else "User usage reset successfully"
        ),
        data={
            "renewed": renewed_expiry is not None,
            "expiry_date": (
                target_user.expiry_date.isoformat()
                if renewed_expiry is not None
                else None
            ),
            "node_sync": node_sync,
        },
    )


@router.post("/", response_model=ResponseModel)
async def create_user(
    request: CreateUser,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # OV_USERNAME_REUSE_V7
    normalized_name = request.name.strip().replace(" ", "_")
    request.name = normalized_name
    check_user = (
        db.query(User)
        .filter(func.lower(User.name) == normalized_name.lower())
        .first()
    )
    if check_user is not None:
        return ResponseModel(
            success=False,
            msg=f"User with this name already exists (owner: {check_user.owner})",
            data=None,
        )

    # OV_DURATION_POLICY_V8
    # OV_RESELLER_DURATION_MAX6_V8_1
    total = _finite_total(request.total)

    if user["type"] == "admin":
        # Reseller UI never sends an exact date. Finite accounts use a selected
        # calendar-month duration; unlimited accounts are always 30 days.
        if total <= 0:
            request.expiry_date = date.today() + timedelta(days=30)
            request.duration_months = 1
            request.device_limit = 1
        else:
            duration_months = request.duration_months
            if duration_months is None:
                raise HTTPException(
                    status_code=400,
                    detail="Select the reseller account duration in months",
                )
            request.expiry_date = _add_calendar_months(date.today(), duration_months)
        try:
            created = crud.create_user(db, request, user["username"], commit=False)
            if total <= 0:
                _change_reseller_entitlements(
                    db, user["username"], unlimited_delta=1,
                    action="user_create", user_uuid=created.uuid, note="unlimited 30-day user",
                )
            else:
                _change_reseller_entitlements(
                    db, user["username"], traffic_delta=total,
                    action="user_create", user_uuid=created.uuid, note="finite traffic user",
                )
            provision_new_user_if_enabled(
                db,
                created.uuid,
                request.anyconnect_enabled,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return ResponseModel(success=True, msg="User created successfully", data=created.name)

    if user["type"] == "main_admin":
        # Main admin finite account: exact date OR relative days/months.
        # Main admin unlimited account: fixed to exactly 30 days.
        if total <= 0:
            request.expiry_date = date.today() + timedelta(days=30)
            request.duration_days = 30
        elif request.duration_days is not None:
            request.expiry_date = date.today() + timedelta(days=int(request.duration_days))
        elif request.duration_months is not None:
            request.expiry_date = _add_calendar_months(date.today(), request.duration_months)

    try:
        created = crud.create_user(
            db,
            request,
            "owner",
            commit=False,
        )
        provision_new_user_if_enabled(
            db,
            created.uuid,
            request.anyconnect_enabled,
        )
        db.commit()
        db.refresh(created)
    except Exception:
        db.rollback()
        raise

    return ResponseModel(
        success=True, msg="User created successfully", data=created.name
    )


@router.put("/{uuid}", response_model=ResponseModel)
async def update_user(
    uuid: str,
    request: UpdateUser,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    target = _owned_user_or_404(db, uuid, user)
    if user["type"] == "admin":
        old_total = _finite_total(target.total)
        new_total = _finite_total(request.total)
        # Reseller cannot edit expiry. Converting a finite account to unlimited
        # starts a fresh fixed 30-day unlimited period; otherwise expiry stays unchanged.
        if old_total > 0 and new_total <= 0:
            request.expiry_date = date.today() + timedelta(days=30)
        else:
            request.expiry_date = target.expiry_date
        # Reseller unlimited accounts are always single-connection.
        if new_total <= 0:
            request.device_limit = 1
        already_used = max(0, int(target.used or 0))
        traffic_delta = 0
        unlimited_delta = 0
        if old_total > 0 and new_total > 0:
            traffic_delta = new_total - old_total
        elif old_total > 0 and new_total <= 0:
            refundable = max(0, old_total - already_used)
            traffic_delta = -refundable
            unlimited_delta = 1
        elif old_total <= 0 and new_total > 0:
            # Unlimited quota is permanent consumption and is not restored.
            traffic_delta = new_total
            unlimited_delta = 0
        try:
            _change_reseller_entitlements(
                db, user["username"], traffic_delta=traffic_delta,
                unlimited_delta=unlimited_delta, action="user_resize",
                user_uuid=uuid,
                note=f"traffic {old_total} -> {new_total}; used={already_used}",
            )
            result = crud.update_user(db, uuid, request, commit=False)
            db.commit()
        except Exception:
            db.rollback()
            raise
    else:
        if user["type"] == "main_admin":
            old_total = _finite_total(target.total)
            new_total = _finite_total(request.total)
            if new_total <= 0:
                # Editing an existing unlimited user must not silently extend it.
                # Only conversion from finite to unlimited starts a new 30-day period.
                request.expiry_date = (
                    date.today() + timedelta(days=30)
                    if old_total > 0
                    else target.expiry_date
                )
        result = crud.update_user(db, uuid, request)
    if result:
        target = crud.get_user_by_uuid(db, uuid)
        used = target.used or 0
        if target.expiry_date >= datetime.today().date() and (target.total == 0 or target.total > used):
            await change_user_status_on_assigned_nodes(uuid, target.name, True, db)
        else:
            await change_user_status_on_assigned_nodes(uuid, target.name, False, db)
    enforce_user_limits()
    return ResponseModel(success=True, msg="User updated successfully", data=result)


@router.post("/{uuid}/renew", response_model=ResponseModel)
async def renew_user(
    uuid: str,
    request: RenewUser,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    target = _owned_user_or_404(db, uuid, actor)
    old_total = _finite_total(target.total)
    old_used = max(0, int(target.used or 0))

    try:
        plan = build_renewal_plan(
            today=date.today(),
            current_expiry=target.expiry_date,
            total=old_total,
            used=old_used,
            duration_days=request.duration_days,
            traffic_action=request.traffic_action,
            add_traffic=request.add_traffic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if actor["type"] == "admin":
        traffic_delta = 0
        if request.traffic_action == "add":
            traffic_delta = int(request.add_traffic)
        elif request.traffic_action == "reset" and old_total > 0:
            traffic_delta = old_total
        if traffic_delta:
            _change_reseller_entitlements(
                db, actor["username"], traffic_delta=traffic_delta,
                action="user_renew", user_uuid=target.uuid,
                note=(f"renew {request.duration_days}d; "
                      f"traffic_action={request.traffic_action}"),
            )

    try:
        if request.traffic_action == "reset":
            await reset_shared_user_usage(target, db)
        target.expiry_date = plan.expiry_date
        target.total = plan.total
        target.used = plan.used
        target.is_active = True
        db.commit()
        db.refresh(target)
    except Exception:
        db.rollback()
        raise

    node_sync = await change_user_status_on_assigned_nodes(
        target.uuid, target.name, True, db
    )

    return ResponseModel(
        success=True,
        msg="User renewed successfully",
        data={
            "uuid": target.uuid,
            "name": target.name,
            "expiry_date": target.expiry_date.isoformat(),
            "total": int(target.total or 0),
            "used": int(target.used or 0),
            "is_active": bool(target.is_active),
            "node_sync": bool(node_sync),
            "subscription_identity_preserved": True,
            "anyconnect_identity_preserved": True,
        },
    )


@router.put("/{uuid}/nodes", response_model=ResponseModel)
async def update_user_nodes(
    uuid: str,
    request: UserNodeAssignmentUpdate,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_current_user),
):
    target = _owned_user_or_404(db, uuid, actor)
    try:
        result = await replace_user_node_assignments(
            target.uuid,
            target.name,
            request.node_ids,
            db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResponseModel(
        success=True,
        msg=(
            "Node assignments updated; some newly assigned nodes are pending reconciliation"
            if result.get("pending_node_ids")
            else "Node assignments updated successfully"
        ),
        data=result,
    )


@router.put("/{uuid}/status", response_model=ResponseModel)
async def change_user_status(
    uuid: str,
    request: UpdateUser,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    target = _owned_user_or_404(db, uuid, user)
    await change_user_status_on_assigned_nodes(uuid, target.name, request.status, db)
    return ResponseModel(success=True, msg="Changed user status successfully")


@router.delete("/{uuid}", response_model=ResponseModel)
async def delete_user(
    uuid: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    # OV_DELETE_USER_REUSE_V7
    target = _owned_user_or_404(db, uuid, user)
    total = _finite_total(target.total)

    # Validate policy before touching node files. The old order could remove
    # node profiles but leave the database row behind and lock the username.
    if user["type"] == "admin" and total <= 0:
        raise HTTPException(
            status_code=403,
            detail="Resellers cannot delete unlimited users",
        )

    node_cleanup = await delete_user_on_all_nodes(target.name, db)

    try:
        if user["type"] == "admin":
            already_used = max(0, int(target.used or 0))
            refundable = max(0, total - already_used)
            _change_reseller_entitlements(
                db, user["username"],
                traffic_delta=-refundable,
                unlimited_delta=0,
                action="user_delete", user_uuid=uuid,
                note=f"finite delete; total={total}; used={already_used}; refunded={refundable}",
            )
        crud.delete_user(db, target.name, commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise

    failed_nodes = node_cleanup.get("failed", [])
    msg = "User deleted successfully"
    if failed_nodes:
        msg += f"; username released, but {len(failed_nodes)} node cleanup(s) need retry"
    return ResponseModel(
        success=True,
        msg=msg,
        data={
            "username_released": True,
            "node_cleanup": node_cleanup,
        },
    )
