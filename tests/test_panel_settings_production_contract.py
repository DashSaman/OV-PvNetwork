import json
import os
import re
import tomllib
import unittest
from pathlib import Path

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "ci-not-a-production-hash")
os.environ.setdefault("MAIN_ADMIN_AUTH_GENERATION", "ci-generation")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-key-not-production-32chars")

from backend import panel_runtime_settings as runtime

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.0.28"


class PanelSettingsProductionContractTests(unittest.TestCase):
    def test_release_version_is_consistent(self):
        self.assertEqual((ROOT / "VERSION").read_text().strip(), EXPECTED_VERSION)
        self.assertIn(f'__version__ = "{EXPECTED_VERSION}"', (ROOT / "backend/version.py").read_text())
        self.assertEqual(json.loads((ROOT / "frontend/package.json").read_text())["version"], EXPECTED_VERSION)
        self.assertEqual(json.loads((ROOT / "manifest.json").read_text())["version"], EXPECTED_VERSION)
        with (ROOT / "pyproject.toml").open("rb") as handle:
            self.assertEqual(tomllib.load(handle)["project"]["version"], EXPECTED_VERSION)

    def test_apply_worker_never_restarts_vpn_or_node_services(self):
        source = (ROOT / "scripts/pvnetwork-panel-settings-apply.py").read_text(encoding="utf-8")
        self.assertIn('ALLOWED_RESTARTS = {"pvnetwork-panel.service"}', source)
        for forbidden in [
            "openvpn-server@server.service",
            "ov-node.service",
            "openvpn-server@pvnetwork-router.service",
            "nginx.service",
        ]:
            self.assertNotIn(f'restart_service("{forbidden}")', source)

    def test_runtime_state_contract_contains_no_secret_fields(self):
        required = {"current_password", "new_password", "password_hash", "jwt", "token", "env"}
        self.assertTrue(required <= runtime.SECRET_KEYS)
        source = (ROOT / "backend/panel_runtime_settings.py").read_text(encoding="utf-8")
        self.assertIn("_contains_secret_key", source)
        self.assertIn("os.replace", source)

    def test_time_bounds_and_canary_contract_are_fixed(self):
        worker = (ROOT / "scripts/pvnetwork-panel-settings-apply.py").read_text(encoding="utf-8")
        self.assertRegex(worker, r"CANARY_PORT\s*=\s*19002")
        self.assertRegex(worker, r"REDIRECT_GRACE_SECONDS\s*=\s*300")
        self.assertIn("timeout=240", worker)
        self.assertIn("_wait_verify(CANARY_PORT, values, 20.0)", worker)
        self.assertIn("_wait_verify(port, values, 30.0)", worker)
        signature = re.search(r"def mint_change_status_token\([^)]*ttl_seconds: int = (\d+)\)", (ROOT / "backend/panel_runtime_settings.py").read_text())
        self.assertIsNotNone(signature)
        self.assertLessEqual(int(signature.group(1)), 900)

    def test_install_and_ci_include_runtime_settings_safety_paths(self):
        installer = (ROOT / "scripts/install-runtime-tools.sh").read_text(encoding="utf-8")
        manager = (ROOT / "scripts/manage.sh").read_text(encoding="utf-8")
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("pvnetwork-panel-settings-apply", installer)
        self.assertIn("migrate_main_admin_generation.py", manager)
        self.assertIn("panel-settings-smoke.mjs", ci)
        self.assertIn("MAX_JS", ci)

    def test_release_notes_cover_safety_and_admin_runtime_settings(self):
        for name in ["docs/RELEASE-NOTES-v1.0.12.md", "docs/RELEASE-NOTES-v1.0.12.fa.md"]:
            path = ROOT / name
            self.assertTrue(path.is_file(), f"missing {name}")
            text = path.read_text(encoding="utf-8").lower()
            for needle in ["1.0.12", "pvn-032", "19002", "300", "openvpn", "node"]:
                self.assertIn(needle, text)

    def test_public_release_metadata_points_to_v1016_asset(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("release_asset"), "pvnetwork-panel-v1.0.28.tar.gz")


if __name__ == "__main__":
    unittest.main()
