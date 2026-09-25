from datetime import date, timedelta
import unittest


class _FakeUser:
    def __init__(self, name, expiry, total=None, used=None, is_active=True):
        self.name = name
        self.expiry_date = expiry
        self.total = total
        self.used = used
        self.is_active = is_active


class RenewalAlertTests(unittest.TestCase):
    """PVN-202/PVN-203 — expiry and traffic-threshold renewal alerts."""

    def setUp(self):
        from backend.operations.renewal_alerts import build_renewal_alerts
        self.build = build_renewal_alerts

    def test_expiry_stages_fire_once_each(self):
        today = date(2026, 9, 25)
        u7 = _FakeUser('a', today + timedelta(days=7))
        u3 = _FakeUser('b', today + timedelta(days=3))
        u1 = _FakeUser('c', today + timedelta(days=1))
        u0 = _FakeUser('d', today)
        u20 = _FakeUser('e', today + timedelta(days=20))
        keys = {item.key.split(':')[3] for item in self.build([u7, u3, u1, u0, u20], today)}
        self.assertEqual({'7', '3', '1', '0'}, keys)
        

    def test_far_expiry_and_inactive_users_are_silent(self):
        today = date(2026, 9, 25)
        far = _FakeUser('far', today + timedelta(days=15))
        inactive = _FakeUser('off', today + timedelta(days=1), is_active=False)
        self.assertEqual([], self.build([far, inactive], today))

    def test_traffic_thresholds_cross_once_at_highest_stage(self):
        u80 = _FakeUser('t80', date(2026, 12, 1), total=100, used=80)
        u95 = _FakeUser('t95', date(2026, 12, 1), total=100, used=95)
        u = _FakeUser('tu', date(2026, 12, 1), total=100, used=100)
        unl = _FakeUser('unl', date(2026, 12, 1), total=0, used=500)
        alerts = {item.key: item.message for item in self.build([u80, u95, u, unl], date(2026, 9, 25))}
        self.assertIn('renew:t:t80:80', alerts)
        self.assertIn('renew:t:t95:90', alerts)
        self.assertIn('renew:t:tu:100', alerts)
        self.assertEqual(3, len(alerts))

    def test_transition_messages_fire_on_appear_and_silent_on_clear(self):
        from backend.operations.renewal_alerts import build_renewal_transition_messages
        old = {'renew:e:x:3': 'old', 'n:1:cpu': 'cpu'}
        new = {'renew:e:x:3': 'kept', 'n:1:cpu': 'cpu'}
        self.assertEqual([], build_renewal_transition_messages(old, new))
        new2 = {'renew:e:y:1': 'y-msg'}
        self.assertEqual(['y-msg'], build_renewal_transition_messages(old, new2))

    def test_monitor_wires_renewal_alerts(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'backend/operations/telegram_monitor.py').read_text(encoding='utf-8')
        self.assertIn('build_renewal_alerts(users)', source)
        # PVN-1018: one consolidated digest per 24h instead of per-tick bursts.
        self.assertIn('renewal_digest_at', source)
        self.assertIn('>= 86400', source)


if __name__ == '__main__':
    unittest.main()
