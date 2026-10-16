from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional, Dict, Literal
import ipaddress
import re


class User(BaseModel):
    name: str
    status: str = "activate"


class ResponseModel(BaseModel):
    success: bool
    msg: str
    data: Optional[Any] = None


class SetSettingsModel(BaseModel):
    tunnel_address: str
    protocol: Literal['udp','tcp']
    ovpn_port: int = Field(ge=1,le=65535)
    set_new_setting: bool

    @field_validator('tunnel_address')
    @classmethod
    def safe_endpoint(cls,value):
        if not value:return value
        try:ipaddress.ip_address(value)
        except ValueError:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',value):raise ValueError('invalid profile endpoint')
        return value

class NativeConfigurationRequest(SetSettingsModel):
    transaction_id: str = Field(pattern=r'^[a-f0-9]{24}$')


class UsersUsage(BaseModel):
    users: Dict[str, int]
    users_rx: Dict[str, int] = Field(default_factory=dict)
    users_tx: Dict[str, int] = Field(default_factory=dict)
