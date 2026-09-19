from pydantic import BaseModel, Field
from datetime import date
from typing import Literal, Optional


class CreateUser(BaseModel):
    name: str = Field(min_length=3, max_length=10)
    total: Optional[int] = Field(default=None, ge=0)
    used: Optional[int] = Field(default=None, ge=0)
    expiry_date: date
    duration_months: Optional[int] = Field(default=None, ge=1, le=6)
    duration_days: Optional[int] = Field(default=None, ge=1, le=3650)
    device_limit: int = Field(default=1, ge=0)
    # None follows the global AnyConnect default.
    anyconnect_enabled: Optional[bool] = None
    # None preserves backward-compatible all-available-node behavior.
    node_ids: Optional[list[int]] = Field(default=None, min_length=1, max_length=256)


class UpdateUser(BaseModel):
    name: str
    total: Optional[int] = Field(default=None, ge=0)
    used: Optional[int] = Field(default=None, ge=0)
    expiry_date: Optional[date]
    status: bool = True
    device_limit: Optional[int] = Field(default=None, ge=0)


class RenewUser(BaseModel):
    duration_days: int = Field(default=30, ge=1, le=3650)
    traffic_action: Literal["preserve", "reset", "add"] = "preserve"
    add_traffic: int = Field(default=0, ge=0)


class UserNodeAssignmentUpdate(BaseModel):
    node_ids: list[int] = Field(min_length=1, max_length=256)


class NodeCreate(BaseModel):
    name: str = Field(max_length=64)
    address: str
    tunnel_address: str = Field(default=None)
    protocol: str = Field(default="tcp")
    ovpn_port: int = Field(default=1194)
    port: int
    key: str = Field(min_length=10, max_length=40)
    status: bool = Field(default=True)
    set_new_setting: bool = Field(default=False)


class AdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=10)
    password: str = Field(min_length=6, max_length=20)
    quota_total: int = Field(default=0, ge=0)
    unlimited_quota_total: int = Field(default=0, ge=0)
    is_active: bool = True


class AdminUpdate(BaseModel):
    username: str = Field(min_length=3, max_length=10)
    password: Optional[str] = Field(default=None, min_length=6, max_length=20)
    quota_total: int = Field(ge=0)
    unlimited_quota_total: Optional[int] = Field(default=None, ge=0)
    is_active: bool
