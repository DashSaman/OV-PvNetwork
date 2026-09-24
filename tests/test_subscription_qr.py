from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / 'frontend' / 'templates' / 'subscription.html'


class SubscriptionQrTests(unittest.TestCase):
    """PVN-211 — smart subscription page: QR codes and per-device guides."""

    def setUp(self):
        self.tpl = TPL.read_text(encoding='utf-8')

    def test_qr_library_is_vendored_same_origin(self):
        lib = ROOT / 'frontend' / 'sub_clients' / 'qr' / 'qrcode.js'
        self.assertTrue(lib.exists() and lib.stat().st_size > 30000)
        source = lib.read_text(encoding='utf-8')
        self.assertIn('Kazuhiko Arase', source)
        # No CDN: the library is served same-origin only.
        self.assertIn('<script src="/sub-clients/qr/qrcode.js"></script>', self.tpl)
        self.assertNotIn('cdn.jsdelivr', self.tpl)
        self.assertNotIn('unpkg.com', self.tpl)

    def test_qr_renders_client_side_with_page_and_per_server_urls(self):
        self.assertIn('PVNETWORK_SUB_QR_V1', self.tpl)
        self.assertIn('window.qrcode(0,"M")', self.tpl)
        self.assertIn('PNQR.show(location.origin+location.pathname,"")', self.tpl)
        self.assertIn("PNQR.show('{{ link }}','{{ node_name }}')", self.tpl)

    def test_qr_overlay_exists_with_close_and_hint(self):
        for marker in ('id="qrOverlay"', 'id="qrClose"', 'id="qrHolder"', 'data-i18n="qrHint"', 'data-i18n="qrClose"'):
            self.assertIn(marker, self.tpl)

    def test_bilingual_catalog_covers_qr_and_devices(self):
        for key in ('qrScan', 'qrPage', 'qrConfig', 'qrHint', 'qrClose', 'qrError',
                    'devWin', 'devMac', 'devIos', 'devAndroid', 'devLinux', 'devRouter'):
            count = len(re.findall(rf'{key}\s*:\s*[\'"]', self.tpl))
            self.assertEqual(2, count, f'{key} must exist in both fa and en catalogs')

    def test_device_guide_cards_render(self):
        for marker in ('data-i18n-html="devWin"', 'data-i18n-html="devRouter"', 'device-grid'):
            self.assertIn(marker, self.tpl)

    def test_notice_attributes_the_qr_library(self):
        notice = (ROOT / 'NOTICE.md').read_text(encoding='utf-8')
        self.assertIn('qrcode-generator', notice)
        self.assertIn('Kazuhiko Arase', notice)

    def test_per_server_qr_button_stops_anchor_navigation(self):
        self.assertIn('event.preventDefault();event.stopPropagation();PNQR.show', self.tpl)


if __name__ == '__main__':
    unittest.main()
