from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PwaAndMobileCardsTests(unittest.TestCase):
    """PVN-1013 — installable admin panel + mobile users-table cards."""

    def test_manifest_exists_with_icons_and_standalone(self):
        import json
        manifest = json.loads((ROOT / 'frontend' / 'public' / 'manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertEqual('standalone', manifest['display'])
        self.assertTrue(manifest['icons'])
        self.assertTrue((ROOT / 'frontend' / 'public' / 'icon.webp').exists())

    def test_index_links_manifest(self):
        html = (ROOT / 'frontend' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('manifest.webmanifest', html)

    def test_users_table_becomes_cards_on_phones(self):
        table = (ROOT / 'frontend' / 'src' / 'components' / 'UserTable.jsx').read_text(encoding='utf-8')
        css = (ROOT / 'frontend' / 'src' / 'components' / 'UserTable.css').read_text(encoding='utf-8')
        self.assertIn('pv-mobile-cards', table)
        self.assertIn('@media (max-width: 640px)', css)
        self.assertIn('display: block', css)
        # The header row is hidden in card mode.
        self.assertIn('thead', css)


if __name__ == '__main__':
    unittest.main()
