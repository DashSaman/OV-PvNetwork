import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class ApplicationNamespaceTests(unittest.TestCase):
    def test_backend_state_paths_are_canonical(self):
        expected = {
            "backend/routers/fleet.py": "/var/lib/pvnetwork-panel/",
            "backend/routers/anyconnect.py": "/etc/pvnetwork/",
            "backend/routers/push.py": "/etc/pvnetwork/push/",
            "backend/operations/telegram_monitor.py": "/var/lib/pvnetwork-panel/",
        }
        for path, value in expected.items():
            with self.subTest(path=path):
                self.assertIn(value, read(path))
    def test_backup_contract_is_owned_by_pvnetwork(self):
        source = read("backend/routers/backups.py")
        for value in (
            "/var/backups/pvnetwork-panel",
            "/var/lib/pvnetwork-panel/restore-jobs",
            "/usr/local/sbin/pvnetwork-panel-backup",
            "/usr/local/sbin/pvnetwork-panel-restore-job",
            "pvnetwork-backup-",
            "pvnetwork-manual-backup-v1",
        ):
            self.assertIn(value, source)

    def test_frontend_uses_canonical_language_storage_key(self):
        source = read("frontend/src/i18n.js")
        self.assertIn("pvnetwork_language", source)
        for path in (
            "frontend/tests/inline-quick-edit-smoke.mjs",
            "frontend/tests/responsive-smoke.mjs",
            "frontend/tests/capture-inline-quick-edit-docs.mjs",
        ):
            self.assertIn("pvnetwork_language", read(path))
    def test_package_metadata_is_pvnetwork_owned(self):
        self.assertIn('name = "pvnetwork-panel"', read("pyproject.toml"))
        lock = json.loads(read("package-lock.json"))
        self.assertEqual("pvnetwork-panel", lock["name"])
        manifest = json.loads(read("manifest.json"))
        self.assertEqual("PVNetwork Panel", manifest["project"])
        self.assertNotIn("base_panel", manifest)

    def test_placeholder_defaults_use_reserved_pvnetwork_domain(self):
        for path in (
            "backend/routers/setting.py",
            "backend/routers/sub.py",
            "backend/node/requests.py",
        ):
            self.assertIn("pvnetwork.example", read(path))

    def test_sqlite_dev_filename_is_canonical_before_db_contract_release(self):
        self.assertIn("pvnetwork-panel.db", read("backend/db/engine.py"))
        self.assertIn("pvnetwork-panel.db", read("backend/alembic.ini"))


if __name__ == "__main__":
    unittest.main()
