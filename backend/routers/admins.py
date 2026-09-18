import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.orm import Session

from backend.db.engine import get_db
from backend.db import crud
from backend.schema.output import Admins, ResponseModel
from backend.schema._input import AdminCreate, AdminUpdate
from backend.auth.auth import get_current_user
from backend.db.models import ResellerCreditTransaction, User
from backend.node.task import delete_user_on_all_nodes


router = APIRouter(prefix="/admin", tags=["Admins"])


class AdminDeleteRequest(BaseModel):
    # OV_ADMIN_DELETE_OPTIONS_V7
    mode: Literal["delete_users", "transfer_users"]
    target_owner: str = "owner"


def _main_admin_only(user: dict):
    if user["type"] != "main_admin":
        raise HTTPException(status_code=403, detail="You do not have permission for this action")


@router.get("/me", response_model=ResponseModel)
async def reseller_profile(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    if user["type"] != "admin":
        raise HTTPException(status_code=403, detail="Reseller account required")
    admin = crud.get_admin_by_username(db, user["username"])
    if not admin:
        raise HTTPException(status_code=404, detail="Reseller not found")
    return ResponseModel(success=True, msg="Reseller profile retrieved", data={
        "username": admin.username,
        "is_active": admin.is_active,
        "quota_total": int(admin.quota_total or 0),
        "quota_used": int(admin.quota_used or 0),
        "quota_remaining": max(0, int(admin.quota_total or 0) - int(admin.quota_used or 0)),
        "unlimited_quota_total": int(admin.unlimited_quota_total or 0),
        "unlimited_quota_used": int(admin.unlimited_quota_used or 0),
        "unlimited_quota_remaining": max(0, int(admin.unlimited_quota_total or 0) - int(admin.unlimited_quota_used or 0)),
    })


@router.get("/", response_model=ResponseModel)
async def get_all_admins(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    _main_admin_only(user)
    result = crud.get_all_admins(db)
    users = crud.get_all_users(db)

    admin_list = []
    for admin in result:
        admin_data = Admins.from_orm(admin)
        admin_data.users_count = sum(1 for u in users if u.owner == admin.username)
        admin_data.quota_remaining = max(0, int(admin.quota_total or 0) - int(admin.quota_used or 0))
        admin_data.unlimited_quota_remaining = max(0, int(admin.unlimited_quota_total or 0) - int(admin.unlimited_quota_used or 0))
        admin_list.append(admin_data)

    return ResponseModel(
        success=True,
        msg="Admins retrieved successfully",
        data=admin_list,
    )


@router.post("/", response_model=ResponseModel)
async def create_admin(
    admin: AdminCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin_only(user)

    existing_admin = crud.get_admin_by_username(db, username=admin.username)
    if existing_admin:
        return ResponseModel(
            success=False, msg="Admin with this username already exists", data=None
        )

    new_admin = crud.create_admin(db, admin)
    if int(new_admin.quota_total or 0) > 0:
        db.add(ResellerCreditTransaction(
            admin_id=new_admin.id,
            amount=0,
            balance_after=0,
            action="quota_limit_create",
            note=f"initial quota_total: {int(new_admin.quota_total or 0)}",
            created_at=int(time.time()),
        ))
        db.commit()
    return ResponseModel(
        success=True,
        msg="Admin created successfully",
        data=Admins.from_orm(new_admin),
    )


@router.put("/")
async def update_admin(
    admin: AdminUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin_only(user)

    existing_admin = crud.get_admin_by_username(db, username=admin.username)
    if not existing_admin:
        return ResponseModel(success=False, msg="Admin not found", data=None)
    if admin.quota_total < int(existing_admin.quota_used or 0):
        raise HTTPException(status_code=409, detail="Credit limit cannot be lower than currently allocated credit")
    requested_unlimited_total = (
        int(existing_admin.unlimited_quota_total or 0)
        if admin.unlimited_quota_total is None
        else int(admin.unlimited_quota_total)
    )
    if requested_unlimited_total < int(existing_admin.unlimited_quota_used or 0):
        raise HTTPException(status_code=409, detail="Unlimited account limit cannot be lower than currently allocated unlimited accounts")

    old_total = int(existing_admin.quota_total or 0)
    old_unlimited_total = int(existing_admin.unlimited_quota_total or 0)
    updated_admin = crud.update_admin(db, existing_admin, admin, commit=False)
    if old_total != int(updated_admin.quota_total or 0):
        db.add(ResellerCreditTransaction(
            admin_id=updated_admin.id, amount=0,
            balance_after=int(updated_admin.quota_used or 0),
            action="quota_limit_change",
            note=f"quota_total: {old_total} -> {int(updated_admin.quota_total or 0)}",
            created_at=int(time.time()),
        ))
    if old_unlimited_total != int(updated_admin.unlimited_quota_total or 0):
        db.add(ResellerCreditTransaction(
            admin_id=updated_admin.id, amount=0,
            balance_after=int(updated_admin.quota_used or 0),
            action="unlimited_limit_change",
            note=f"unlimited_quota_total: {old_unlimited_total} -> {int(updated_admin.unlimited_quota_total or 0)}",
            created_at=int(time.time()),
        ))
    db.commit()
    return ResponseModel(
        success=True,
        msg="Admin updated successfully",
        data=Admins.from_orm(updated_admin),
    )



@router.post("/{username}/delete", response_model=ResponseModel)
async def delete_admin_with_users(
    username: str,
    request: AdminDeleteRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # OV_ADMIN_DELETE_OPTIONS_V7
    _main_admin_only(user)
    existing_admin = crud.get_admin_by_username(db, username=username)
    if not existing_admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    if request.target_owner != "owner":
        raise HTTPException(status_code=400, detail="Users can only be transferred to owner")

    owned_users = db.query(User).filter(User.owner == username).all()
    cleanup_results = []

    if request.mode == "delete_users" and owned_users:
        semaphore = asyncio.Semaphore(4)

        async def cleanup_one(item):
            async with semaphore:
                return await delete_user_on_all_nodes(item.name, db)

        cleanup_results = await asyncio.gather(
            *(cleanup_one(item) for item in owned_users),
            return_exceptions=True,
        )

    try:
        if request.mode == "transfer_users":
            for item in owned_users:
                item.owner = "owner"
        else:
            for item in owned_users:
                db.delete(item)
        db.flush()
        db.delete(existing_admin)
        db.commit()
    except Exception:
        db.rollback()
        raise

    failed_node_cleanups = 0
    if request.mode == "delete_users":
        for result in cleanup_results:
            if isinstance(result, Exception):
                failed_node_cleanups += 1
            else:
                failed_node_cleanups += len(result.get("failed", []))

    return ResponseModel(
        success=True,
        msg=(
            "Admin deleted and users transferred to owner"
            if request.mode == "transfer_users"
            else "Admin and all owned users deleted"
        ),
        data={
            "mode": request.mode,
            "affected_users": len(owned_users),
            "failed_node_cleanups": failed_node_cleanups,
        },
    )


@router.delete("/{username}")
async def delete_admin(
    username: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin_only(user)

    existing_admin = crud.get_admin_by_username(db, username=username)
    if not existing_admin:
        return ResponseModel(success=False, msg="Admin not found", data=None)
    if db.query(User).filter(User.owner == username).count():
        raise HTTPException(status_code=409, detail="Move or delete this reseller's users before deleting the reseller")

    crud.delete_admin(db, existing_admin)
    return ResponseModel(
        success=True,
        msg="Admin deleted successfully",
        data=None,
    )


@router.get("/{username}/transactions", response_model=ResponseModel)
async def reseller_transactions(
    username: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _main_admin_only(user)
    admin = crud.get_admin_by_username(db, username)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    rows = (
        db.query(ResellerCreditTransaction)
        .filter(ResellerCreditTransaction.admin_id == admin.id)
        .order_by(ResellerCreditTransaction.id.desc())
        .limit(limit).all()
    )
    data = [{
        "id": row.id, "amount": row.amount, "balance_after": row.balance_after,
        "action": row.action, "user_uuid": row.user_uuid,
        "note": row.note, "created_at": row.created_at,
    } for row in rows]
    return ResponseModel(success=True, msg="Transactions retrieved successfully", data=data)
