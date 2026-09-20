import os
import unittest

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

import jwt
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import auth
from backend.config import config
from backend.db.models import Admin, ApiToken


class AuthRegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Admin.__table__.create(self.engine)
        ApiToken.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.old_username = config.ADMIN_USERNAME
        self.old_generation = config.MAIN_ADMIN_AUTH_GENERATION
        config.ADMIN_USERNAME = "ci-admin"
        config.MAIN_ADMIN_AUTH_GENERATION = "gen-current"

    def tearDown(self):
        self.db.close()
        config.ADMIN_USERNAME = self.old_username
        config.MAIN_ADMIN_AUTH_GENERATION = self.old_generation

    def assert_rejected(self, token):
        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_user(token=token, db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def signed(self, payload, secret=None):
        return jwt.encode(
            payload,
            secret or config.JWT_SECRET_KEY,
            algorithm=auth.ALGORITHM,
        )

    def test_expired_admin_jwt_is_rejected(self):
        self.assert_rejected(self.signed({"sub": "alice", "type": "admin", "exp": 1}))

    def test_wrong_signature_is_rejected(self):
        token = self.signed(
            {"sub": "alice", "type": "admin", "exp": 4102444800},
            secret="wrong-secret-not-production-32chars",
        )
        self.assert_rejected(token)

    def test_missing_subject_is_rejected(self):
        token = self.signed({"type": "admin", "exp": 4102444800})
        self.assert_rejected(token)

    def test_unknown_type_is_rejected(self):
        token = self.signed({"sub": "alice", "type": "owner", "exp": 4102444800})
        self.assert_rejected(token)

    def test_forged_main_admin_subject_is_rejected(self):
        token = self.signed({
            "sub": "other-admin", "type": "main_admin",
            "gen": "gen-current", "exp": 4102444800,
        })
        self.assert_rejected(token)

    def test_stale_main_admin_generation_is_rejected(self):
        token = self.signed({
            "sub": "ci-admin", "type": "main_admin",
            "gen": "gen-old", "exp": 4102444800,
        })
        self.assert_rejected(token)

    def test_disabled_admin_invalidates_already_issued_jwt(self):
        admin = Admin(username="alice", password="unused", is_active=True)
        self.db.add(admin)
        self.db.commit()
        token = self.signed({"sub": "alice", "type": "admin", "exp": 4102444800})
        principal = auth.get_current_user(token=token, db=self.db)
        self.assertEqual(principal["username"], "alice")

        admin.is_active = False
        self.db.commit()
        self.assert_rejected(token)


if __name__ == "__main__":
    unittest.main()


class CorsCsrfPostureTests(unittest.TestCase):
    def test_cors_exact_origin_semantics_and_project_wiring(self):
        import asyncio
        from pathlib import Path
        from starlette.middleware.cors import CORSMiddleware

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        cors = CORSMiddleware(
            app,
            allow_origins=["https://trusted.example"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        async def preflight(origin):
            sent = []
            scope = {
                "type": "http", "http_version": "1.1", "method": "OPTIONS",
                "scheme": "https", "path": "/state", "raw_path": b"/state",
                "query_string": b"", "server": ("test", 443),
                "client": ("127.0.0.1", 12345),
                "headers": [
                    (b"origin", origin.encode()),
                    (b"access-control-request-method", b"PUT"),
                ],
            }
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            async def send(message):
                sent.append(message)
            await cors(scope, receive, send)
            start_msg = next(m for m in sent if m["type"] == "http.response.start")
            return {k.decode().lower(): v.decode() for k, v in start_msg["headers"]}

        trusted = asyncio.run(preflight("https://trusted.example"))
        untrusted = asyncio.run(preflight("https://evil.example"))
        self.assertEqual(trusted.get("access-control-allow-origin"), "https://trusted.example")
        self.assertNotEqual(untrusted.get("access-control-allow-origin"), "https://evil.example")

        root = Path(__file__).resolve().parents[1]
        app_source = (root / "backend/app.py").read_text(encoding="utf-8")
        self.assertIn("allow_origins=cors_origins", app_source)
        self.assertIn("allow_credentials=True", app_source)

    def test_browser_auth_is_bearer_not_ambient_cookie(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        api_source = (root / "frontend/src/services/api.js").read_text(encoding="utf-8")
        auth_source = (root / "backend/auth/auth.py").read_text(encoding="utf-8")
        self.assertIn("Authorization", api_source)
        self.assertIn("Bearer ${token}", api_source)
        self.assertNotIn("document.cookie", api_source)
        self.assertIn("OAuth2PasswordBearer", auth_source)
        self.assertNotIn("set_cookie", auth_source)

    def test_frontend_has_no_unreviewed_raw_html_sinks(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "frontend/src"
        hits = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".js", ".jsx", ".ts", ".tsx"}:
                continue
            text = path.read_text(encoding="utf-8")
            for needle in ("dangerouslySetInnerHTML", "document.write", ".innerHTML =", ".innerHTML="):
                if needle in text:
                    hits.append(f"{path.name}:{needle}")
        self.assertEqual(hits, [])
