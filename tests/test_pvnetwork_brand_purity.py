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
