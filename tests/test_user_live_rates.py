from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UserLiveRatesTests(unittest.TestCase):
    """PVN-1016 — per-user live speed badge + professional chart."""

    def test_rates_module_samples_usage_and_maps_uuids(self):
        source = (ROOT / 'backend' / 'operations' / 'user_live_rates.py').read_text(encoding='utf-8')
        self.assertIn('get_users_usage', source)
        self.assertIn('client_username', source)
        self.assertIn('rates_bps_by_uuid', source)
        # Delta window guards: too-short and stale samples produce no rate.
        self.assertIn('0.4 <= elapsed <= 30.0', source)

    def test_presence_endpoint_exposes_rates(self):
        source = (ROOT / 'backend' / 'routers' / 'users.py').read_text(encoding='utf-8')
        self.assertIn('get_user_live_rates()', source)
        self.assertIn('"rates_bps_by_uuid": rates', source)

    def test_users_page_passes_rates_into_table(self):
        page = (ROOT / 'frontend' / 'src' / 'pages' / 'UserManagement.jsx').read_text(encoding='utf-8')
        table = (ROOT / 'frontend' / 'src' / 'components' / 'UserTable.jsx').read_text(encoding='utf-8')
        self.assertIn('ratesByUuid={presenceRates}', page)
        self.assertIn('ratesByUuid', table)
        self.assertIn('pv-speed-cell', table)
        self.assertIn('pv-speed-down', table)
        self.assertIn('pv-speed-up', table)

    def test_chart_is_lazy_and_recharts(self):
        page = (ROOT / 'frontend' / 'src' / 'pages' / 'ServerStats.jsx').read_text(encoding='utf-8')
        chart = (ROOT / 'frontend' / 'src' / 'components' / 'LiveAreaChart.jsx').read_text(encoding='utf-8')
        self.assertIn("lazy(() => import('../components/LiveAreaChart')", page)
        self.assertIn('recharts', chart)
        self.assertIn('AreaChart', chart)

    def test_speed_chip_styles_exist(self):
        css = (ROOT / 'frontend' / 'src' / 'components' / 'UserTable.css').read_text(encoding='utf-8')
        self.assertIn('.pv-live-speed', css)


if __name__ == '__main__':
    unittest.main()
