from pathlib import Path
from urllib.parse import urlsplit
import ipaddress
from pydantic import Field,field_validator
from pydantic_settings import BaseSettings,SettingsConfigDict


class Settings(BaseSettings):
    service_port:int=Field(default=9090,ge=1,le=65535)
    api_key:str=Field(min_length=24,max_length=512)
    debug:str='WARNING'
    doc:bool=False
    # The authenticated HTTPS endpoint is limited by the installer source-IP firewall.
    listen_host:str='0.0.0.0'  # nosec B104
    tls_certfile:str='/etc/pvnetwork-node/tls.crt'
    tls_keyfile:str='/etc/pvnetwork-node/tls.key'
    panel_url:str=''
    panel_ca_file:str|None=None
    openvpn_status_file:str='/var/log/openvpn-status.log'
    hook_key:str=Field(default='',max_length=128)
    accounting_file:str|None=None
    accounting_spool_dir:str|None=None
    openvpn_management_socket:str='/var/run/openvpn-server/server.sock'
    model_config=SettingsConfigDict(env_file=Path(__file__).resolve().parents[1]/'.env',extra='forbid')

    @field_validator('panel_url')
    @classmethod
    def secure_controller_url(cls,value):
        if not value:return value
        parsed=urlsplit(value)
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('plain controller origin required')
        local=parsed.hostname=='localhost'
        try:local=local or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:pass
        if parsed.scheme!='https' and not (parsed.scheme=='http' and local):raise ValueError('HTTPS required for remote controller callbacks')
        return value.rstrip('/')


settings=Settings()
