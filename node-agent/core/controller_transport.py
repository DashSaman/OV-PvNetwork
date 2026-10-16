import ssl
import hmac
import ipaddress
import urllib.request
from urllib.parse import urlsplit
from fastapi import HTTPException
from core.config import settings


def controller_ssl_context():
    # Settings permit HTTPS or an explicit loopback HTTP URL. Custom CA trust
    # is installed over the approved SSH channel; verification is mandatory.
    return ssl.create_default_context(cafile=settings.panel_ca_file)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,new_url):return None


def open_controller(request,timeout):
    parsed=urlsplit(request.full_url)
    local=parsed.hostname=='localhost'
    try:local=local or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:pass
    if not parsed.hostname or parsed.username or parsed.password or (parsed.scheme!='https' and not (parsed.scheme=='http' and local)):
        raise ValueError('HTTPS or explicit loopback HTTP required')
    # Never propagate the node credential to a redirect target or an env proxy.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=controller_ssl_context()))
    return opener.open(request,timeout=timeout)


def require_local_hook(request):
    if not request.client or request.client.host not in {'127.0.0.1','::1'}:raise HTTPException(status_code=403,detail='Local access only')
    if not settings.hook_key:raise HTTPException(status_code=503,detail='Local hook authentication is not configured')
    supplied=request.headers.get('X-PVNetwork-Hook-Key','')
    if not supplied or not hmac.compare_digest(supplied.encode(),settings.hook_key.encode()):raise HTTPException(status_code=401,detail='Invalid local hook key')
