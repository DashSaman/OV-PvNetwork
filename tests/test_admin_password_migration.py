import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

from backend.auth.hash import verify_password
from scripts.migrate_admin_password_hash import parse, rewrite


class AdminPasswordMigrationTests(unittest.TestCase):
    def test_plaintext_admin_password_is_replaced_with_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "ADMIN_USERNAME=admin\n"
                "ADMIN_" "PASSWORD=correct-horse-battery-staple\n"
                "JWT_" "SECRET_KEY=test-secret\n",
                encoding="utf-8",
            )
            changed = rewrite(env_path)
            self.assertTrue(changed)
            text = env_path.read_text(encoding="utf-8")
            self.assertNotIn("ADMIN_" "PASSWORD=", text)
            values = parse(text.splitlines())
            self.assertTrue(
                verify_password(
                    "correct-horse-battery-staple",
                    values["ADMIN_PASSWORD_HASH"],
                )
            )
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_existing_hash_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "ADMIN_USERNAME=admin\n"
                "ADMIN_PASSWORD_HASH=$2b$12$abcdefghijklmnopqrstuu1234567890123456789012\n",
                encoding="utf-8",
            )
            before = env_path.read_text(encoding="utf-8")
            changed = rewrite(env_path)
            self.assertFalse(changed)
            self.assertEqual(env_path.read_text(encoding="utf-8"), before)
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
