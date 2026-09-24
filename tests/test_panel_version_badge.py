from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PanelVersionBadgeContractTests(unittest.TestCase):
    def test_dashboard_fetches_public_healthz_version(self):
        source = (ROOT / 'frontend/src/pages/ServerStats.jsx').read_text(encoding='utf-8')
        self.assertIn("fetch('/healthz'", source)
        self.assertIn('data.version', source)
        self.assertIn('setPanelVersion', source)

    def test_version_badge_renders_next_to_live_badge(self):
        source = (ROOT / 'frontend/src/pages/ServerStats.jsx').read_text(encoding='utf-8')
        self.assertIn('ov-live-badge', source)
        self.assertIn('ov-version-badge', source)
        self.assertIn('panelVersion &&', source)

    def test_version_badge_style_exists(self):
        source = (ROOT / 'frontend/src/pages/ServerStats.jsx').read_text(encoding='utf-8')
        self.assertIn('.ov-version-badge {', source)
        self.assertIn('tabular-nums', source)


if __name__ == '__main__':
    unittest.main()
