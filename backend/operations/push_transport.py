"""Web Push delivery restricted to approved origins and pinned public addresses."""
from __future__ import annotations

import ipaddress
import re
import socket
import ssl
from urllib.parse import urlsplit

from pywebpush import webpush as _webpush
from requests import Response
from urllib3 import HTTPSConnectionPool
from urllib3.util import Timeout

from backend.config import config


DEFAULT_ORIGINS = frozenset({
    'https://fcm.googleapis.com',
    'https://updates.push.services.mozilla.com',
    'https://web.push.apple.com',
})
MAX_RESPONSE_BYTES = 32768


def _parsed_url(endpoint: str):
    if not isinstance(endpoint, str) or len(endpoint) > 8192:
        raise ValueError('Invalid push endpoint')
    if any(ord(char) <= 32 or ord(char) >= 127 for char in endpoint) or '\\' in endpoint:
        raise ValueError('Invalid push endpoint')
    if re.search(r'%(?:0[0-9a-f]|1[0-9a-f]|7f)', endpoint, re.I):
        raise ValueError('Invalid push endpoint')
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname or ''
        port = parsed.port or 443
    except ValueError:
        raise ValueError('Invalid push endpoint') from None
    if (parsed.scheme != 'https' or parsed.username is not None or parsed.password is not None
            or parsed.fragment or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', host)
            or parsed.netloc != host + (f':{port}' if ':' in parsed.netloc else '')
            or not 1 <= port <= 65535):
        raise ValueError('Invalid push endpoint')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('Push endpoint must be a provider hostname')
    return parsed, host, port


def validate_endpoint(endpoint: str) -> str:
    parsed, host, port = _parsed_url(endpoint)
    origin = 'https://' + parsed.netloc
    allowed = set(DEFAULT_ORIGINS)
    for extra in config.PUSH_ALLOWED_ORIGINS.split(','):
        if not extra.strip():
            continue
        item = extra.strip()
        value, _extra_host, _extra_port = _parsed_url(item)
        if value.path or value.query or value.fragment:
            raise ValueError('Push origin configuration must contain HTTPS origins only')
        allowed.add(item)
    provider_subdomain = port == 443 and any(
        host.endswith('.' + suffix) for suffix in ('push.apple.com', 'notify.windows.com')
    ) and ':' not in parsed.netloc
    if origin not in allowed and not provider_subdomain:
        raise ValueError('Push provider origin is not approved')
    return endpoint


class PushSession:
    """Small pywebpush session interface; no proxy, redirect or DNS re-resolution."""
    def post(self, url, *, data, headers, timeout=12):
        validate_endpoint(url)
        parsed, host, port = _parsed_url(url)
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = sorted({record[4][0] for record in records})
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError('Push provider must resolve only to public addresses')
        request_headers = dict(headers)
        request_headers['Host'] = parsed.netloc
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        # The pool connects to this literal IP. Original hostname is retained
        # for SNI and certificate verification, closing DNS rebinding at use.
        pool = HTTPSConnectionPool(addresses[0], port=port, cert_reqs=ssl.CERT_REQUIRED,
            assert_hostname=host, server_hostname=host, maxsize=1, block=True,
            timeout=Timeout(total=12, connect=4, read=8))
        raw = None
        try:
            raw = pool.urlopen('POST', path, body=data, headers=request_headers,
                redirect=False, retries=False, preload_content=False)
            result = Response()
            result.status_code = int(raw.status)
            result.reason = raw.reason
            result.headers.update(raw.headers)
            result.url = url
            result._content = raw.read(MAX_RESPONSE_BYTES + 1, decode_content=False)
            if len(result._content) > MAX_RESPONSE_BYTES:
                raise ValueError('Push provider response exceeds limit')
            return result
        finally:
            if raw is not None:
                raw.close()
                raw.release_conn()
            pool.close()


def send_push(*, subscription_info, **kwargs):
    # Stored subscriptions are revalidated, including those written by old code.
    validate_endpoint(subscription_info.get('endpoint'))
    kwargs.pop('requests_session', None)
    kwargs.pop('curl', None)
    kwargs['timeout'] = 12
    kwargs['verbose'] = False
    return _webpush(subscription_info=subscription_info, requests_session=PushSession(), **kwargs)
