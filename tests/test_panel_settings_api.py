import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi import HTTPException
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

os.environ.setdefault("ADMIN_USERNAME", "owner")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("MAIN_ADMIN_AUTH_GENERATION", "gen-old")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")
os.environ.setdefault("SUBSCRIPTION_PATH", "sub")

from backend.auth.hash import hash_password, verify_password
from backend.config import config
from backend.db.models import Admin, AuditLog, Base, PrincipalSecurity
from backend import panel_runtime_settings as runtime


@compiles(BigInteger, "sqlite")
def _compile_bigint_as_integer_for_sqlite(_type, _compiler, **_kw):
    return "INTEGER"


ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = ROOT / "backend/routers/panel_settings.py"
WORKER_PATH = ROOT / "scripts/pvnetwork-panel-settings-apply.py"


def load_router(testcase):
    testcase.assertTrue(ROUTER_PATH.exists(), "panel settings router must exist")
    spec = importlib.util.spec_from_file_location("panel_settings_router_test", ROUTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_worker():
    spec = importlib.util.spec_from_file_location("panel_settings_worker_api_test", WORKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PanelSettingsApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.router = load_router(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.current_password = "current-password-123"
        self.current_hash = hash_password(self.current_password)
        self.live_env = self.root / ".env"
        self.live_env.write_text(
            "ADMIN_USERNAME=owner\n"
            f"ADMIN_PASSWORD_HASH={self.current_hash}\n"
            "MAIN_ADMIN_AUTH_GENERATION=gen-old\n"
            "URLPATH=oldpath\nVITE_URLPATH=oldpath\n"
            "JWT_SECRET_KEY=ci-jwt-secret-not-production-32chars\n"
            "SUBSCRIPTION_PATH=sub\nPORT=19001\n",
            encoding="utf-8",
        )
        os.chmod(self.live_env, 0o600)
        self.jobs = self.root / "jobs"
        self.staging = self.root / "staging"
        self.lock = self.root / "apply.lock"
        self.transition = self.root / "transition.json"
        self.patchers = [
            patch.object(runtime, "LIVE_ENV", self.live_env, create=True),
            patch.object(runtime, "JOB_DIR", self.jobs),
            patch.object(runtime, "STAGING_ROOT", self.staging, create=True),
            patch.object(runtime, "LOCK_FILE", self.lock),
            patch.object(runtime, "TRANSITION_FILE", self.transition),
        ]
        for item in self.patchers:
            item.start()
        self.db.add(
            Admin(
                id=1,
                username="reseller",
                password=hash_password("reseller-password"),
                is_active=True,
                quota_total=0,
                quota_used=0,
                unlimited_quota_total=0,
                unlimited_quota_used=0,
            )
        )
        self.db.add(
            PrincipalSecurity(
                id=1,
                username="owner",
                principal_type="main_admin",
                totp_secret_encrypted="encrypted-secret",
                totp_enabled=True,
                updated_at=1,
            )
        )
        self.db.commit()
        self.main_user = {"username": "owner", "type": "main_admin"}

    def tearDown(self):
        for item in reversed(self.patchers):
            item.stop()
        self.db.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def request(self, **values):
        payload = {"current_password": self.current_password}
        payload.update(values)
        return self.router.PanelSettingsApplyIn(**payload)

    async def assert_http(self, status, request, user):
        with self.assertRaises(HTTPException) as ctx:
            await self.router.apply_panel_settings(request, db=self.db, user=user)
        self.assertEqual(ctx.exception.status_code, status)
        return ctx.exception

    async def test_api_token_and_delegated_admin_cannot_apply(self):
        req = self.request(new_path="nextpanel")
        await self.assert_http(
            403,
            req,
            {"username": "owner", "type": "main_admin", "auth_kind": "api_token"},
        )
        await self.assert_http(403, req, {"username": "reseller", "type": "admin"})

    async def test_wrong_current_password_is_noop(self):
        before = self.live_env.read_bytes()
        req = self.router.PanelSettingsApplyIn(current_password="wrong", new_path="nextpanel")
        with patch.object(runtime, "spawn_apply_helper") as spawn:
            await self.assert_http(401, req, self.main_user)
        self.assertEqual(self.live_env.read_bytes(), before)
        self.assertFalse(self.staging.exists())
        spawn.assert_not_called()

    async def test_noop_and_validation_errors_are_422(self):
        cases = [
            self.request(new_path="OLDPATH"),
            self.request(new_path="api"),
            self.request(new_username="reseller"),
            self.request(new_username="ab"),
            self.request(new_password="short"),
            self.request(new_password=self.current_password),
        ]
        for req in cases:
            with self.subTest(req=req.model_dump()):
                await self.assert_http(422, req, self.main_user)

    async def test_new_password_rejects_more_than_72_utf8_bytes(self):
        req = self.request(new_password="x" * 73)
        with patch.object(runtime, "spawn_apply_helper", return_value=1):
            await self.assert_http(422, req, self.main_user)

    async def test_concurrent_apply_returns_409(self):
        fd = runtime.acquire_apply_lock()
        try:
            await self.assert_http(
                409,
                self.request(new_path="nextpanel"),
                self.main_user,
            )
        finally:
            os.close(fd)

    async def test_path_only_apply_stages_secret_free_job_without_replacement_jwt(self):
        with patch.object(runtime, "spawn_apply_helper", return_value=2222) as spawn:
            response = await self.router.apply_panel_settings(
                self.request(new_path="nextpanel"),
                db=self.db,
                user=self.main_user,
            )
        data = response.data
        self.assertEqual(data["target_path"], "nextpanel")
        self.assertIsNone(data.get("pending_access_token"))
        runtime.verify_change_status_token(data["status_token"], data["change_id"])
        job = runtime.read_job_state(data["change_id"])
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["old_path"], "oldpath")
        self.assertEqual(job["new_path"], "nextpanel")
        self.assertEqual(job["changed_fields"], ["path"])
        serialized = json.dumps(job).lower()
        self.assertNotIn(self.current_password.lower(), serialized)
        self.assertNotIn("password_hash", serialized)
        self.assertNotIn("jwt", serialized)
        spawn.assert_called_once()

    async def test_credential_rotation_returns_pending_token_and_records_totp_row_id(self):
        with patch.object(runtime, "spawn_apply_helper", return_value=3333):
            response = await self.router.apply_panel_settings(
                self.request(new_username="new-owner", new_password="new-password-456"),
                db=self.db,
                user=self.main_user,
            )
        data = response.data
        self.assertTrue(data["pending_access_token"])
        payload = jwt.decode(
            data["pending_access_token"],
            config.JWT_SECRET_KEY,
            algorithms=["HS256"],
        )
        self.assertEqual(payload["sub"], "new-owner")
        self.assertEqual(payload["type"], "main_admin")
        self.assertNotEqual(payload["gen"], "gen-old")
        job = runtime.read_job_state(data["change_id"])
        self.assertEqual(job["principal_security_id"], 1)
        self.assertEqual(job["old_username"], "owner")
        self.assertEqual(job["new_username"], "new-owner")
        candidate = Path(runtime.STAGING_ROOT) / data["change_id"] / "candidate.env"
        text = candidate.read_text(encoding="utf-8")
        self.assertNotIn("new-password-456", text)
        hashed = next(
            line.split("=", 1)[1]
            for line in text.splitlines()
            if line.startswith("ADMIN_PASSWORD_HASH=")
        )
        self.assertTrue(verify_password("new-password-456", hashed))

    async def test_job_status_uses_change_token_and_hides_internal_fields(self):
        with patch.object(runtime, "spawn_apply_helper", return_value=4444):
            applied = await self.router.apply_panel_settings(
                self.request(new_path="nextpanel"),
                db=self.db,
                user=self.main_user,
            )
        data = applied.data
        response = await self.router.get_panel_settings_job(
            data["change_id"],
            change_token=data["status_token"],
        )
        public = response.data
        self.assertEqual(public["change_id"], data["change_id"])
        self.assertEqual(public["status"], "queued")
        for forbidden in [
            "expected_env_sha256",
            "principal_security_id",
            "staging_dir",
            "password_hash",
            "jwt",
            "token",
        ]:
            self.assertNotIn(forbidden, public)
        with self.assertRaises(HTTPException) as ctx:
            await self.router.get_panel_settings_job(
                data["change_id"],
                change_token=data["status_token"] + "x",
            )
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_status_route_has_no_browser_jwt_dependency_and_router_is_registered(self):
        route = next(
            item
            for item in self.router.router.routes
            if getattr(item, "path", "")
            == "/security/panel-settings/jobs/{change_id}"
        )
        self.assertEqual(route.dependant.dependencies, [])
        exports = (ROOT / "backend/routers/__init__.py").read_text(encoding="utf-8")
        self.assertIn("panel_settings_router", exports)


class PanelSettingsWorkerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.worker = load_worker()
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add(
                PrincipalSecurity(
                    id=7,
                    username="owner",
                    principal_type="main_admin",
                    totp_secret_encrypted="encrypted-secret",
                    totp_enabled=True,
                    updated_at=1,
                )
            )
            db.commit()
        self.factory = lambda: Session(self.engine)
        self.job = {
            "change_id": "change-a",
            "old_path": "oldpath",
            "new_path": "newpath",
            "old_username": "owner",
            "new_username": "new-owner",
            "principal_security_id": 7,
            "changed_fields": ["username", "path"],
            "audit_actor": "owner",
        }

    def tearDown(self):
        self.engine.dispose()

    def test_username_migration_preserves_totp_and_rollback_restores_it(self):
        self.worker.migrate_principal_security(
            self.job,
            forward=True,
            session_factory=self.factory,
        )
        with Session(self.engine) as db:
            row = db.get(PrincipalSecurity, 7)
            self.assertEqual(row.username, "new-owner")
            self.assertTrue(row.totp_enabled)
            self.assertEqual(row.totp_secret_encrypted, "encrypted-secret")
        self.worker.migrate_principal_security(
            self.job,
            forward=False,
            session_factory=self.factory,
        )
        with Session(self.engine) as db:
            row = db.get(PrincipalSecurity, 7)
            self.assertEqual(row.username, "owner")
            self.assertTrue(row.totp_enabled)
            self.assertEqual(row.totp_secret_encrypted, "encrypted-secret")

    def test_terminal_audit_is_idempotent_and_secret_free(self):
        self.worker.write_terminal_audit(
            self.job,
            "complete",
            session_factory=self.factory,
        )
        self.worker.write_terminal_audit(
            self.job,
            "complete",
            session_factory=self.factory,
        )
        with Session(self.engine) as db:
            rows = db.query(AuditLog).all()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.action, "SETTINGS_APPLY")
            self.assertEqual(row.request_id, "settings-change-a-complete")
            self.assertTrue(row.success)
            self.assertIn("path=oldpath->newpath", row.resource)
            self.assertIn("username=changed", row.resource)
            self.assertNotIn("password", row.resource.lower())
            self.assertNotIn("secret", row.resource.lower())


if __name__ == "__main__":
    unittest.main()
