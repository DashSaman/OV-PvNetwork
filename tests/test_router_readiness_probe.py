from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODAL = ROOT / 'frontend' / 'src' / 'components' / 'AddUserModal.jsx'


class RouterReadinessProbeTests(unittest.TestCase):
    """PVN-1011 — the Router checkbox probes live node capability."""

    def setUp(self):
        self.modal = MODAL.read_text(encoding='utf-8')

    def test_toggle_probes_selected_nodes(self):
        self.assertIn('handleRouterToggle', self.modal)
        self.assertIn('probeRouterReadiness', self.modal)
        self.assertIn('`/router-openvpn/nodes/${nodeId}`', self.modal)
        self.assertIn('Boolean(d.enabled && d.healthy)', self.modal)

    def test_inline_readiness_hint_with_enable_instructions(self):
        self.assertIn('routerReadiness.checking', self.modal)
        self.assertIn('routerStatusNone', self.modal)
        self.assertIn('routerStatusReady', self.modal)
        # The none-ready hint must teach the enable path.
        none_block = self.modal[self.modal.index("routerStatusNone"):]
        self.assertIn('Router / MikroTik', none_block[:600])

    def test_failures_translate_to_actionable_messages(self):
        self.assertIn('routerFriendlyError', self.modal)
        self.assertIn('not enabled on this node', self.modal)
        self.assertIn('routerErrNotEnabled', self.modal)
        self.assertIn('routerErrNotHealthy', self.modal)

    def test_readiness_keys_exist_in_all_catalogs(self):
        langs = ['en', 'fa', 'ar', 'es', 'id', 'ja', 'pt_BR', 'ru', 'tr', 'uk', 'vi', 'zh_CN', 'zh_TW']
        for lang in langs:
            catalog = json.loads((ROOT / 'frontend' / 'src' / 'lang' / f'{lang}.json').read_text(encoding='utf-8'))
            for key in ('routerStatusChecking', 'routerStatusNone', 'routerStatusReady',
                        'routerErrNotEnabled', 'routerErrNotHealthy', 'routerErrUpgrade'):
                self.assertIn(key, catalog, f'{lang}:{key}')


if __name__ == '__main__':
    unittest.main()
