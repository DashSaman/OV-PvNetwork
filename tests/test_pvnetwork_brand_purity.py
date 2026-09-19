import re
import subprocess
import unittest
from pathlib import Path


class PVNetworkBrandPurityTests(unittest.TestCase):
    def test_tracked_tree_has_no_former_upstream_panel_identifier(self):
        root = Path(__file__).resolve().parents[1]
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=root
        ).decode().split("\0")
        tracked = [item for item in tracked if item]

        stem = "o" + "v"
        product = "p" + "a" + "n" + "e" + "l"
        forms = [
            stem + "-" + product,
            stem + "_" + product,
            stem + " " + product,
            stem + product,
        ]
        pattern = re.compile("|".join(re.escape(item) for item in forms), re.I)
        violations = []

        for rel in tracked:
            if pattern.search(rel):
                violations.append(f"path:{rel}")
            path = root / rel
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"\0" in data:
                continue
            text = data.decode("utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    violations.append(f"content:{rel}:{lineno}")

        self.assertEqual([], violations, "\n".join(violations[:200]))


    def test_sqlite_upgrade_reuses_single_existing_database(self):
        import tempfile
        from backend.db.engine import _resolve_default_sqlite_path

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            existing = data_dir / "previous-install.db"
            existing.write_bytes(b"sqlite-placeholder")
            self.assertEqual(existing, _resolve_default_sqlite_path(data_dir))

    def test_node_request_defaults_tunnel_to_node_address(self):
        from backend.node.requests import NodeRequests

        request = NodeRequests("192.0.2.10", 9090, "demo-key")
        self.assertEqual("192.0.2.10", request.tunnel_address)

    def test_runtime_config_paths_are_pvnetwork_owned(self):
        root = Path(__file__).resolve().parents[1]
        anyconnect = (root / "backend/routers/anyconnect.py").read_text()
        push = (root / "backend/routers/push.py").read_text()
        self.assertIn("/etc/pvnetwork-panel/", anyconnect)
        self.assertIn("/etc/pvnetwork-panel/", push)

    def test_release_metadata_versions_are_consistent(self):
        import json
        import tomllib

        root = Path(__file__).resolve().parents[1]
        version = (root / "VERSION").read_text().strip()
        manifest = json.loads((root / "manifest.json").read_text())
        with (root / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        backend_version = {}
        exec((root / "backend/version.py").read_text(), backend_version)
        frontend = json.loads((root / "frontend/package.json").read_text())
        frontend_lock = json.loads((root / "frontend/package-lock.json").read_text())
        self.assertEqual(version, manifest["version"])
        self.assertEqual(version, project["version"])
        self.assertEqual(version, backend_version["__version__"])
        self.assertEqual(version, frontend["version"])
        self.assertEqual(version, frontend_lock["version"])
        self.assertEqual("pvnetwork-panel-frontend", frontend["name"])

    def test_webpush_runtime_dependency_is_declared(self):
        import tomllib

        root = Path(__file__).resolve().parents[1]
        with (root / "pyproject.toml").open("rb") as handle:
            dependencies = tomllib.load(handle)["project"]["dependencies"]
        self.assertTrue(
            any(item.lower().startswith("pywebpush") for item in dependencies),
            "pywebpush must be declared because backend.routers.push imports it",
        )

    def test_operational_helpers_and_units_are_version_controlled(self):
        root = Path(__file__).resolve().parents[1]
        required = [
            "scripts/pvnetwork-panel-backup",
            "scripts/pvnetwork-panel-restore-job",
            "scripts/pvnetwork-panel-smoke-test",
            "ops/systemd/pvnetwork-panel.service",
            "ops/systemd/pvnetwork-panel-backup.service",
            "ops/systemd/pvnetwork-panel-backup.timer",
            "ops/systemd/pvnetwork-panel-monitor.service",
            "ops/systemd/pvnetwork-panel-monitor.timer",
            "ops/systemd/pvnetwork-panel-smoke.service",
            "ops/systemd/pvnetwork-panel-smoke.timer",
            "ops/systemd/pvnetwork-panel-user-notifier.service",
            "ops/systemd/pvnetwork-panel-user-notifier.timer",
            "ops/systemd/pvnetwork-panel-healthcheck.service",
            "ops/systemd/pvnetwork-panel-healthcheck.timer",
        ]
        missing = [rel for rel in required if not (root / rel).is_file()]
        self.assertEqual([], missing)

    def test_critical_background_jobs_have_pvnetwork_units(self):
        root = Path(__file__).resolve().parents[1]
        required = [
            "scripts/pvnetwork-usage-sync",
            "scripts/pvnetwork-sub-push-sender.py",
            "ops/systemd/pvnetwork-usage-sync.service",
            "ops/systemd/pvnetwork-usage-sync.timer",
            "ops/systemd/pvnetwork-bandwidth-reconcile.service",
            "ops/systemd/pvnetwork-bandwidth-reconcile.timer",
            "ops/systemd/pvnetwork-sub-push.service",
            "ops/systemd/pvnetwork-sub-push.timer",
        ]
        missing = [rel for rel in required if not (root / rel).is_file()]
        self.assertEqual([], missing)
        sender = (root / "scripts/pvnetwork-sub-push-sender.py").read_text()
        self.assertIn("/etc/pvnetwork-panel/push/vapid-private.pem", sender)
        self.assertIn("https://example.invalid", sender)

    def test_panel_healthcheck_also_guards_external_node_api(self):
        root = Path(__file__).resolve().parents[1]
        health = (root / "scripts/healthcheck.sh").read_text()
        self.assertIn("pvnetwork-panel.service", health)
        self.assertIn("ov-node.service", health)
        self.assertIn("/opt/ov-node/.env", health)

    def test_lifecycle_cli_is_pvnetwork_owned(self):
        root = Path(__file__).resolve().parents[1]
        install = (root / "install-local.sh").read_text()
        runtime_tools = (root / "scripts/install-runtime-tools.sh").read_text()
        manage = (root / "scripts/manage.sh").read_text()
        bootstrap = (root / "install.sh").read_text()
        self.assertIn("install-runtime-tools.sh", install)
        self.assertIn("/usr/local/sbin/pvnetwork", runtime_tools)
        self.assertIn("/etc/pvnetwork-panel", manage)
        self.assertIn("/var/backups/pvnetwork-panel/lifecycle", manage)
        self.assertIn("PVNETWORK_REF", manage)
        self.assertIn("PVNETWORK_REF", bootstrap)

    def test_tracked_tree_has_no_retired_internal_brand_aliases(self):
        root = Path(__file__).resolve().parents[1]
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=root
        ).decode().split("\0")
        tracked = [item for item in tracked if item]
        repo_slug = "DashSaman/" + "O" + "V-PvNetwork"
        retired = [
            "O" + "V-PvNetwork",
            "o" + "v-pvnetwork",
            "o" + "v" + "p" + "v",
            "O" + "V" + "P" + "V" + "_",
        ]
        pattern = re.compile("|".join(re.escape(item) for item in retired), re.I)
        retired_upper_prefix = "O" + "V" + "_"
        violations = []
        for rel in tracked:
            path = root / rel
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if b"\0" in data:
                continue
            text = data.decode("utf-8", errors="ignore").replace(repo_slug, "")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line) or retired_upper_prefix in line:
                    violations.append(f"content:{rel}:{lineno}")
        self.assertEqual([], violations, "\n".join(violations[:200]))

    def test_pvnetwork_owned_runtime_contract_is_declared(self):
        root = Path(__file__).resolve().parents[1]
        install = (root / "install-local.sh").read_text()
        manage = (root / "scripts/manage.sh").read_text()
        manifest = (root / "manifest.json").read_text()
        self.assertIn("/opt/pvnetwork-panel", install)
        self.assertIn("pvnetwork-panel.service", install)
        self.assertIn("/opt/pvnetwork-panel", manage)
        self.assertIn("pvnetwork-panel.service", manage)
        self.assertIn('"DashSaman/OV-PvNetwork"', manifest)
