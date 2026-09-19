import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = (
    "installer.py",
    "install-local.sh",
    "install.sh",
    "scripts/manage.sh",
    "scripts/healthcheck.sh",
    "scripts/configure_env.py",
    "scripts/verify.sh",
    "scripts/export-production.sh",
)
FORBIDDEN = ("ov" + "-panel", "ov" + "panel", "ov" + "pv")


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


class RuntimeNamespaceTests(unittest.TestCase):
    def test_runtime_files_do_not_reference_legacy_namespace(self):
        failures = []
        for path in RUNTIME_FILES:
            lowered = text(path).lower()
            for token in FORBIDDEN:
                if token in lowered:
                    failures.append(f"{path}: {token}")
        self.assertEqual([], failures, "\n".join(failures))
    def test_fresh_installer_uses_canonical_root_service_cli_and_config(self):
        source = text("install-local.sh")
        self.assertIn('APP="/opt/pvnetwork-panel"', source)
        self.assertIn('/etc/systemd/system/pvnetwork-panel.service', source)
        self.assertIn('WorkingDirectory=/opt/pvnetwork-panel', source)
        self.assertIn('/usr/local/sbin/pvnetwork', source)
        self.assertIn('/etc/pvnetwork', source)

    def test_lifecycle_manager_targets_only_canonical_runtime(self):
        source = text("scripts/manage.sh")
        self.assertIn('APP="/opt/pvnetwork-panel"', source)
        self.assertIn('STATE="/etc/pvnetwork"', source)
        self.assertIn('BACKUPS="/var/backups/pvnetwork-panel"', source)
        self.assertIn('MANAGER="/usr/local/sbin/pvnetwork"', source)
        self.assertIn('pvnetwork-panel.service', source)
        self.assertIn('/tmp/pvnetwork-update.', source)

    def test_health_and_verification_scripts_use_canonical_service(self):
        for path in ("scripts/healthcheck.sh", "scripts/verify.sh"):
            source = text(path)
            self.assertIn("pvnetwork-panel.service", source)
        self.assertIn("/opt/pvnetwork-panel", text("scripts/healthcheck.sh"))
        self.assertIn("/opt/pvnetwork-panel", text("scripts/verify.sh"))
    def test_python_installer_is_owned_by_pvnetwork(self):
        source = text("installer.py")
        self.assertIn("PVNetwork Panel", source)
        self.assertIn("/opt/pvnetwork-panel", source)
        self.assertIn("pvnetwork-panel.service", source)
        self.assertIn("DashSaman/OV-PvNetwork", source)

    def test_export_and_env_helpers_default_to_canonical_root(self):
        self.assertIn('/opt/pvnetwork-panel', text("scripts/configure_env.py"))
        self.assertIn('/opt/pvnetwork-panel', text("scripts/export-production.sh"))


if __name__ == "__main__":
    unittest.main()
