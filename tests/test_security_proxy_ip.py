import os
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import SecuritySettings
from backend.routers import security as security_router
from backend import security_middleware as middleware


class DummyClient:
    def __init__(self, host):
        self.host = host


class DummyRequest:
    def __init__(self, peer, forwarded="", path="/api/login", method="GET"):
        self.client = DummyClient(peer)
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}
        self.url = types.SimpleNamespace(path=path)
        self.method = method


class ClientIpTests(unittest.TestCase):
    def canonical(self):
        value = getattr(middleware, "client_ip", None)
        self.assertIsNotNone(value, "public canonical client_ip helper is required")
        return value

    def test_loopback_proxy_uses_final_forwarded_address(self):
        request = DummyRequest("127.0.0.1", "203.0.113.9, 198.51.100.25")
        self.assertEqual(self.canonical()(request), "198.51.100.25")

    def test_direct_peer_ignores_spoofed_forwarded_address(self):
        request = DummyRequest("192.0.2.40", "203.0.113.9")
        self.assertEqual(self.canonical()(request), "192.0.2.40")

    def test_invalid_forwarded_address_falls_back_to_loopback_peer(self):
        request = DummyRequest("127.0.0.1", "not-an-ip")
        self.assertEqual(self.canonical()(request), "127.0.0.1")

    def test_ipv6_loopback_uses_final_forwarded_address(self):
        request = DummyRequest("::1", "2001:db8::10, 2001:db8::25")
        self.assertEqual(self.canonical()(request), "2001:db8::25")


class AllowlistEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_allowlist_uses_same_final_forwarded_ip_as_middleware(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        SecuritySettings.__table__.create(engine)
        Session = sessionmaker(bind=engine)
        with Session() as db:
            db.add(SecuritySettings(id=1, allowed_cidrs="[]"))
            db.commit()
            request = DummyRequest("127.0.0.1", "203.0.113.9, 198.51.100.25")
            payload = security_router.SettingsIn(
                rate_limit_enabled=True,
                rate_limit_per_minute=120,
                ip_allowlist_enabled=True,
                allowed_cidrs=["198.51.100.25/32"],
            )
            try:
                result = await security_router.put(
                    payload, request=request, db=db, u={"type": "main_admin"}
                )
            except HTTPException as exc:
                self.fail(f"canonical client IP was rejected: {exc.detail}")
            self.assertTrue(result.success)


class RateLimitProxyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        middleware._hits.clear()
        middleware._login_hits.clear()
        middleware._cache.update(at=0, v=None)

    async def test_leading_spoof_values_share_one_login_bucket(self):
        guard = middleware.SecurityMiddleware(app=lambda scope, receive, send: None)
        requests = [
            DummyRequest("127.0.0.1", "203.0.113.1, 198.51.100.25"),
            DummyRequest("127.0.0.1", "203.0.113.2, 198.51.100.25"),
        ]

        async def call_next(_request):
            return types.SimpleNamespace(status_code=200)

        with patch.object(middleware, "LOGIN_RATE_LIMIT_PER_MINUTE", 1), patch.object(
            middleware,
            "cfg",
            return_value={"rate": False, "limit": 120, "allow": False, "cidrs": []},
        ):
            first = await guard.dispatch(requests[0], call_next)
            second = await guard.dispatch(requests[1], call_next)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.headers.get("Retry-After"), "60")


if __name__ == "__main__":
    unittest.main()
