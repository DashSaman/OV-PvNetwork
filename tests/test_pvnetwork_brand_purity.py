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
