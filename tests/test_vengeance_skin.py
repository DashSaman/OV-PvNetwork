from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / 'frontend' / 'src' / 'vengeance-skin.css'
MAIN = ROOT / 'frontend' / 'src' / 'main.jsx'


class VengeanceSkinTests(unittest.TestCase):
    """PVN-1015 — professional skin, token-level and fully rollbackable."""

    def test_skin_is_token_level_and_scoped(self):
        css = SKIN.read_text(encoding='utf-8')
        # Token overrides only; no layout/position rules that could break pages.
        self.assertIn('--accent-color', css)
        self.assertIn('backdrop-filter', css)
        self.assertNotIn('position:', css)
        self.assertNotIn('display:', css)
        self.assertNotIn('z-index', css)

    def test_skin_respects_reduced_motion(self):
        css = SKIN.read_text(encoding='utf-8')
        self.assertIn('prefers-reduced-motion: reduce', css)

    def test_skin_loaded_after_core_css(self):
        main = MAIN.read_text(encoding='utf-8')
        self.assertIn('vengeance-skin.css', main)
        self.assertLess(main.index('index.css') if 'index.css' in main else main.index('page-hardening.css'),
                        main.index('vengeance-skin.css'))


if __name__ == '__main__':
    unittest.main()
