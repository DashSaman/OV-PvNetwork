import ast
import hashlib
import json
import os
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")
os.environ.setdefault("MIRZA_API_KEY", "m" * 32)

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend import panel_runtime_settings as runtime
from backend.db.models import ApiToken, Base, User
from backend.routers import backups, panel_settings, security, users
from backend.routers import mirza

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER_CASES = ["../other", "..%2Fother", "' OR 1=1 --", '" OR "1"="1', "<script>globalThis.pwned=1</script>"]


class IdentifierRegressionTests(unittest.TestCase):
    def test_backup_ids_cannot_escape_backup_root(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(backups, "BACKUP_ROOT", Path(tmp)):
            for value in IDENTIFIER_CASES:
                with self.subTest(value=value), self.assertRaises(HTTPException) as ctx:
                    backups._backup_directory(value)
                self.assertEqual(ctx.exception.status_code, 404)

    def test_panel_status_token_cannot_be_replayed_for_other_change(self):
        token = runtime.mint_change_status_token("change-one")
        runtime.verify_change_status_token(token, "change-one")
        with self.assertRaises(ValueError):
            runtime.verify_change_status_token(token, "change-two")

    def test_delegated_admin_cannot_see_another_owner_user(self):
        target = type("Target", (), {"owner": "other", "uuid": "u-2"})()
        with patch.object(users.crud, "get_user_by_uuid", return_value=target):
            with self.assertRaises(HTTPException) as ctx:
                users._owned_user_or_404(None, "u-2", {"type": "admin", "username": "alice"})
        self.assertEqual(ctx.exception.status_code, 404)


class DatabaseInputRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        for index, name in enumerate(("victim", "other"), start=1):
            self.db.add(User(
                id=index, uuid=f"user-{index}", name=name,
                total=1024, used=0, last_node_usage=0,
                expiry_date=date(2030, 1, 1), is_active=True,
                owner="owner", device_limit=1,
            ))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_mirza_username_injection_never_selects_adjacent_user(self):
        before = [(row.uuid, row.name) for row in self.db.query(User).order_by(User.id)]
        for payload in ("victim' OR 1=1 --", 'victim" OR "1"="1'):
            with self.subTest(payload=payload), self.assertRaises(HTTPException) as ctx:
                await mirza.get_mirza_user(payload, db=self.db, _="m" * 32)
            self.assertIn(ctx.exception.status_code, {400, 404, 422})
            after = [(row.uuid, row.name) for row in self.db.query(User).order_by(User.id)]
            self.assertEqual(after, before)


class RedactionRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_security_token_listing_never_exposes_hash_or_raw_token(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine)
        try:
            db.add(security.SecuritySettings(id=1, allowed_cidrs="[]"))
            db.add(ApiToken(
                id=1, name="demo", token_prefix="pvn_demo",
                token_hash=hashlib.sha256(b"pvn_demo_secret").hexdigest(),
                scopes=json.dumps(["settings:read"]), expires_at=None,
                revoked_at=None, created_at=int(time.time()), last_used_at=None,
                created_by="owner",
            ))
            db.commit()
            result = await security.get(db=db, u={"type": "main_admin", "username": "owner"})
            encoded = json.dumps(result.data)
            self.assertNotIn("token_hash", encoded)
            self.assertNotIn("pvn_demo_secret", encoded)
            self.assertNotIn(hashlib.sha256(b"pvn_demo_secret").hexdigest(), encoded)
        finally:
            db.close()
            engine.dispose()

    async def test_panel_job_status_hides_internal_secret_fields(self):
        change_id = "change-safe"
        token = runtime.mint_change_status_token(change_id)
        state = {
            "change_id": change_id,
            "status": "queued",
            "old_path": "panel",
            "new_path": "newpanel",
            "changed_fields": ["password"],
            "password_hash": "secret-hash",
            "pending_access_token": "secret-jwt",
            "candidate_env": "secret-env",
            "staging_dir": "/secret/stage",
        }
        with patch.object(runtime, "read_job_state", return_value=state):
            result = await panel_settings.get_panel_settings_job(change_id, token)
        encoded = json.dumps(result.data)
        for forbidden in ("secret-hash", "secret-jwt", "secret-env", "/secret/stage"):
            self.assertNotIn(forbidden, encoded)


class SqlInterpolationGuardTests(unittest.TestCase):
    def test_runtime_sql_text_calls_do_not_interpolate_user_values(self):
        unsafe = []
        for path in (ROOT / "backend").rglob("*.py"):
            if "alembic/versions" in path.as_posix():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                if name not in {"text", "_session_text"}:
                    continue
                arg = node.args[0]
                bad = isinstance(arg, ast.JoinedStr) or (isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod)) or (
                    isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "format"
                )
                if bad:
                    unsafe.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        self.assertEqual(unsafe, [])


class RouteProtectionInventoryTests(unittest.TestCase):
    def dependency_names(self, dependant):
        names = set()
        stack = list(getattr(dependant, "dependencies", []) or [])
        while stack:
            dep = stack.pop()
            call = getattr(dep, "call", None)
            if call is not None:
                names.add(getattr(call, "__name__", ""))
            stack.extend(getattr(dep, "dependencies", []) or [])
        return names

    def test_every_api_route_has_recognized_protection_boundary(self):
        from backend.routers import all_routers
        from backend.routers.anyconnect import router as anyconnect_router, integration_router
        from backend.routers.router_openvpn import router as router_openvpn_router

        allowed_dependency = {"get_current_user", "require_mirza_key", "node_key_header"}
        explicitly_guarded = {
            "/api/login",
            "/api/security/panel-settings/jobs/{change_id}",
        }
        failures = []
        for router in [*all_routers, router_openvpn_router, anyconnect_router, integration_router]:
            for route in router.routes:
                path = "/api" + getattr(route, "path", "")
                if path in explicitly_guarded:
                    continue
                deps = self.dependency_names(getattr(route, "dependant", None))
                if not deps.intersection(allowed_dependency):
                    failures.append((path, sorted(deps), getattr(route.endpoint, "__name__", "")))
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
