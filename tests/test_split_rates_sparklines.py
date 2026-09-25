from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SplitRatesTests(unittest.TestCase):
    """PVN-1017 — separate per-user download/upload + node sparklines."""

    def test_rates_module_computes_split_axes(self):
        source = (ROOT / 'backend' / 'operations' / 'user_live_rates.py').read_text(encoding='utf-8')
        self.assertIn('users_rx', source)
        self.assertIn('users_tx', source)
        self.assertIn('"down": round(down * 8, 1)', source)
        self.assertIn('"up": round(up * 8, 1)', source)
        # Combined stays authoritative for legacy nodes.
        self.assertIn('users = payload.get("users")', source)

    def test_user_table_shows_separate_arrows(self):
        table = (ROOT / 'frontend' / 'src' / 'components' / 'UserTable.jsx').read_text(encoding='utf-8')
        self.assertIn('"↓ "', table.replace("'", '"'))
        self.assertIn('"↑ "', table.replace("'", '"'))
        self.assertIn('pv-live-speed', table)

    def test_node_sparkline_exists_and_is_lazy(self):
        spark = (ROOT / 'frontend' / 'src' / 'components' / 'NodeSparkline.jsx').read_text(encoding='utf-8')
        page = (ROOT / 'frontend' / 'src' / 'pages' / 'ServerStats.jsx').read_text(encoding='utf-8')
        self.assertIn('recharts', spark)
        self.assertIn('AreaChart', spark)
        self.assertIn("lazy(() => import('../components/NodeSparkline')", page)
        self.assertIn('nodeHistoryRef', page)

    def test_renewal_permission_modal_is_weekly(self):
        tpl = (ROOT / 'frontend' / 'templates' / 'subscription.html').read_text(encoding='utf-8')
        self.assertIn('weekKey', tpl)
        self.assertIn('modalDismissKey) === weekKey()', tpl)


if __name__ == '__main__':
    unittest.main()
