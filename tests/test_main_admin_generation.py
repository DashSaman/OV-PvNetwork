import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import jwt
from fastapi import HTTPException

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

from backend.auth import auth
from backend.config import config

ROOT = Path(__file__).resolve().parents[1]


def raw_token(username: str, generation: str):
    return jwt.encode(
        {"sub": username, "type": "main_admin", "gen": generation, "exp": 4102444800},
        config.JWT_SECRET_KEY,
        algorithm=auth.ALGORITHM,
    )

class MainAdminGenerationTests(unittest.TestCase):
    def setUp(self):
        self.original_username = config.ADMIN_USERNAME
        self.original_generation = config.MAIN_ADMIN_AUTH_GENERATION
        config.ADMIN_USERNAME = "ci-admin"
        config.MAIN_ADMIN_AUTH_GENERATION = "gen-current"

    def tearDown(self):
        config.ADMIN_USERNAME = self.original_username
        config.MAIN_ADMIN_AUTH_GENERATION = self.original_generation

    def test_generation_config_exists(self):
        self.assertTrue(hasattr(config, "MAIN_ADMIN_AUTH_GENERATION"))
        self.assertTrue(str(getattr(config, "MAIN_ADMIN_AUTH_GENERATION", "")).strip())

    def test_old_main_admin_generation_is_rejected(self):
        token = raw_token("ci-admin", "gen-old")
        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_user(token=token, db=Mock())
        self.assertEqual(ctx.exception.status_code, 401)

    def test_main_admin_subject_must_match_config(self):
        token = raw_token("old-admin", getattr(config, "MAIN_ADMIN_AUTH_GENERATION", "legacy"))
        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_user(token=token, db=Mock())
        self.assertEqual(ctx.exception.status_code, 401)

    def test_mint_main_admin_token_uses_configured_expiry(self):
        import time
        previous = config.JWT_ACCESS_TOKEN_EXPIRES
        config.JWT_ACCESS_TOKEN_EXPIRES = 90
        try:
            token = auth.mint_main_admin_token("ci-admin", "gen-expiry")
            payload = jwt.decode(
                token, config.JWT_SECRET_KEY, algorithms=[auth.ALGORITHM]
            )
            remaining = int(payload["exp"]) - int(time.time())
            self.assertGreaterEqual(remaining, 85)
            self.assertLessEqual(remaining, 95)
        finally:
            config.JWT_ACCESS_TOKEN_EXPIRES = previous

    def test_mint_main_admin_token_binds_generation(self):
        self.assertTrue(hasattr(auth, "mint_main_admin_token"))
        token = auth.mint_main_admin_token("ci-admin", "gen-123")
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[auth.ALGORITHM])
        self.assertEqual(payload["sub"], "ci-admin")
        self.assertEqual(payload["type"], "main_admin")
        self.assertEqual(payload["gen"], "gen-123")

class MainAdminGenerationMigrationTests(unittest.TestCase):
    def _module(self):
        script = ROOT / "scripts/migrate_main_admin_generation.py"
        self.assertTrue(script.exists(), "generation migration script must exist")
        spec = importlib.util.spec_from_file_location("migrate_main_admin_generation", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_generation_bootstrap_is_idempotent_and_private(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("ADMIN_USERNAME=admin\nURLPATH=panel\n", encoding="utf-8")
            first = module.ensure_generation(env_path)
            second = module.ensure_generation(env_path)
            self.assertEqual(first, second)
            self.assertGreaterEqual(len(first), 24)
            self.assertIn(f"MAIN_ADMIN_AUTH_GENERATION={first}", env_path.read_text(encoding="utf-8"))
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_install_and_update_bootstrap_generation(self):
        install = (ROOT / "install-local.sh").read_text(encoding="utf-8")
        manage = (ROOT / "scripts/manage.sh").read_text(encoding="utf-8")
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("MAIN_ADMIN_AUTH_GENERATION=", install)
        self.assertIn("migrate_main_admin_generation.py", manage)
        self.assertIn("MAIN_ADMIN_AUTH_GENERATION=CHANGE_ME_GENERATED", example)


if __name__ == "__main__":
    unittest.main()
