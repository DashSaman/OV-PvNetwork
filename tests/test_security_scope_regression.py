import hashlib
import json
import os
import time
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

from fastapi import HTTPException
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from backend.auth import auth
from backend.db.models import ApiToken, PrincipalSecurity, SecuritySettings
from backend.routers import security as security_router
from backend import security_middleware


@compiles(BigInteger, "sqlite")
def _compile_bigint_as_integer(_type, _compiler, **_kw):
    return "INTEGER"


class DummyRequest:
    def __init__(self, path, method, token):
        self.url = types.SimpleNamespace(path=path)
        self.method = method
        self.headers = {"authorization": f"Bearer {token}"}
        self.client = types.SimpleNamespace(host="127.0.0.1")


class ScopeRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        for table in (ApiToken.__table__, PrincipalSecurity.__table__, SecuritySettings.__table__):
            table.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(SecuritySettings(id=1, allowed_cidrs="[]"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def add_token(self, raw, scopes, *, expires_at=None, revoked_at=None):
        row = ApiToken(
            name="test", token_prefix=raw[:12],
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            scopes=json.dumps(scopes), expires_at=expires_at,
            revoked_at=revoked_at, created_at=int(time.time()),
            created_by="owner",
        )
        self.db.add(row)
        self.db.commit()
        return row

    def assert_auth_rejected(self, raw):
        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_user(token=raw, db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_api_token_cannot_be_interactive_main_admin(self):
        user = {"username": "owner", "type": "main_admin", "auth_kind": "api_token"}
        with self.assertRaises(HTTPException) as ctx:
            security_router.main(user)
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_api_token_cannot_create_security_token(self):
        user = {"username": "owner", "type": "main_admin", "auth_kind": "api_token"}
        request = security_router.TokenIn(name="forbidden", scopes=["settings:write"])
        with self.assertRaises(HTTPException) as ctx:
            await security_router.token(request, db=self.db, u=user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_unrelated_prefix_is_rejected_even_if_hash_exists(self):
        raw = "badprefix_secret-value"
        self.add_token(raw, ["settings:read"])
        self.assert_auth_rejected(raw)

    def test_supported_prefixes_are_accepted(self):
        for raw in ("pvn_demo-token-one", "ovp_demo-token-two"):
            self.add_token(raw, ["settings:read"])
            principal = auth.get_current_user(token=raw, db=self.db)
            self.assertEqual(principal["auth_kind"], "api_token")

    def test_expired_and_revoked_tokens_are_rejected(self):
        expired = "pvn_expired-token"
        revoked = "pvn_revoked-token"
        self.add_token(expired, ["settings:read"], expires_at=int(time.time()) - 1)
        self.add_token(revoked, ["settings:read"], revoked_at=int(time.time()))
        self.assert_auth_rejected(expired)
        self.assert_auth_rejected(revoked)

    async def scoped_request(self, method, path, raw):
        guard = security_middleware.ApiScopeMiddleware(app=lambda scope, receive, send: None)
        request = DummyRequest(path, method, raw)

        async def call_next(_request):
            return types.SimpleNamespace(status_code=200)

        with patch.object(security_middleware, "SessionLocal", self.Session):
            return await guard.dispatch(request, call_next)

    async def test_lookalike_settings_path_is_not_classified_as_users(self):
        raw = "pvn_settings-lookalike"
        self.add_token(raw, ["settings:read"])
        response = await self.scoped_request("GET", "/api/settings/users-report", raw)
        self.assertEqual(response.status_code, 200)

    async def test_operations_routes_do_not_cross_scope_boundaries(self):
        cases = [
            ("GET", "/api/operations/users/user-1/history", "users:read", True),
            ("GET", "/api/operations/users/user-1/history", "settings:read", False),
            ("POST", "/api/operations/users/bulk", "users:write", True),
            ("POST", "/api/operations/users/bulk", "settings:write", False),
            ("POST", "/api/operations/users/transfer", "nodes:write", True),
            ("POST", "/api/operations/users/transfer", "users:write", False),
            ("GET", "/api/operations/audit", "audit:read", True),
            ("GET", "/api/operations/audit", "settings:read", False),
            ("POST", "/api/operations/rebalance", "nodes:write", True),
            ("POST", "/api/operations/rebalance", "settings:write", False),
            ("GET", "/api/anyconnect/users/user-1/password", "users:read", True),
            ("GET", "/api/anyconnect/users/user-1/password", "settings:read", False),
            ("POST", "/api/anyconnect/users/user-1/password", "users:write", True),
            ("GET", "/api/router-openvpn/users/user-1/nodes/1", "users:read", True),
            ("GET", "/api/router-openvpn/users/user-1/nodes/1", "settings:read", False),
            ("PUT", "/api/router-openvpn/nodes/1", "nodes:write", True),
            ("PUT", "/api/router-openvpn/nodes/1", "settings:write", False),
        ]
        for index, (method, path, scope, allowed) in enumerate(cases):
            raw = f"pvn_operations-{index}"
            self.add_token(raw, [scope])
            response = await self.scoped_request(method, path, raw)
            self.assertEqual(
                response.status_code,
                200 if allowed else 403,
                f"{method} {path} with {scope}",
            )

    async def test_scope_read_write_matrix(self):
        cases = [
            ("GET", "/api/users/", "users:read", True),
            ("PUT", "/api/users/demo", "users:read", False),
            ("PUT", "/api/users/demo", "users:write", True),
            ("GET", "/api/nodes/", "nodes:read", True),
            ("POST", "/api/fleet/jobs/demo/retry", "nodes:write", True),
            ("GET", "/api/audit/", "audit:read", True),
            ("GET", "/api/security/", "settings:read", True),
            ("PUT", "/api/security/", "settings:write", True),
        ]
        for index, (method, path, scope, allowed) in enumerate(cases):
            raw = f"pvn_matrix-{index}"
            self.add_token(raw, [scope])
            response = await self.scoped_request(method, path, raw)
            self.assertEqual(
                response.status_code,
                200 if allowed else 403,
                f"{method} {path} with {scope}",
            )


if __name__ == "__main__":
    unittest.main()
