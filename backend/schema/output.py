from pydantic import BaseModel, Field
from datetime import date
from typing import Any, Optional


class ResponseModel(BaseModel):
    success: bool
    msg: str
    data: Optional[Any] = None


class Users(BaseModel):
    # OV_USER_SORT_ID_V2
    id: int
    name: str
    is_active: bool
    total: Optional[float] = None
    used: Optional[float] = None
    expiry_date: date
    owner: str
    uuid: str
    device_limit: int = 1
    online_count: int = 0
    is_online: bool = False
    anyconnect_configured: bool = False
    anyconnect_enabled: bool = False
    anyconnect_password_available: bool = False

    class Config:
        from_attributes = True


class ServerInfo(BaseModel):
    cpu: float
    memory_total: int
    memory_used: int
    memory_percent: float
    disk_total: int
    disk_used: int
    disk_percent: float
    uptime: int

    class Config:
        from_attributes = True


class Settings(BaseModel):
    subscription_url_prefix: str
    subscription_path: str


class Admins(BaseModel):
    id: int
    username: str
    users_count: int = 0
    is_active: bool = True
    quota_total: int = 0
    quota_used: int = 0
    quota_remaining: int = 0
    unlimited_quota_total: int = 0
    unlimited_quota_used: int = 0
    unlimited_quota_remaining: int = 0

    class Config:
        from_attributes = True
