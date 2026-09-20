from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RolloutRuntimeGuardTests(unittest.TestCase):
    def test_node_healthcheck_uses_get_with_json_body_for_sync_status(self):
        text = (ROOT / "scripts/healthcheck.sh").read_text(encoding="utf-8")
        block = text.split("check_node_three()", 1)[1].split("if ! check_node_three", 1)[0]
        self.assertIn('/sync/status', block)
        self.assertIn('--data "$payload"', block)
        self.assertRegex(block, r"curl[\s\\\n\S]*?-X[ \t]+GET[\s\\\n\S]*?/sync/status")

    def test_panel_smoke_does_not_source_secret_bearing_env(self):
        text = (ROOT / "scripts/pvnetwork-panel-smoke-test").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?m)^\s*(?:source|\.)\s+\.?/?\.env\s*$")
        self.assertIn('PORT="$(read_env_value PORT)"', text)
        self.assertIn('URLPATH="$(read_env_value URLPATH)"', text)


if __name__ == "__main__":
    unittest.main()
