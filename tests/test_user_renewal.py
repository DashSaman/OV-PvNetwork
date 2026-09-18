import unittest
from datetime import date

from backend.operations.user_renewal import build_renewal_plan, unlimited_reset_expiry


class RenewalPlanTests(unittest.TestCase):
    def test_expired_unlimited_extends_from_today(self):
        plan = build_renewal_plan(
            today=date(2026, 9, 18),
            current_expiry=date(2026, 8, 1),
            total=0,
            used=0,
            duration_days=30,
            traffic_action="preserve",
            add_traffic=0,
        )
        self.assertEqual(plan.expiry_date, date(2026, 10, 18))
        self.assertEqual(plan.total, 0)
        self.assertEqual(plan.used, 0)
        self.assertTrue(plan.activate)
    def test_active_user_extends_from_current_expiry(self):
        plan = build_renewal_plan(
            today=date(2026, 9, 18),
            current_expiry=date(2026, 10, 1),
            total=100,
            used=50,
            duration_days=30,
            traffic_action="preserve",
            add_traffic=0,
        )
        self.assertEqual(plan.expiry_date, date(2026, 10, 31))
        self.assertEqual(plan.total, 100)
        self.assertEqual(plan.used, 50)

    def test_reset_keeps_total_and_zeroes_usage(self):
        plan = build_renewal_plan(
            today=date(2026, 9, 18), current_expiry=date(2026, 9, 1),
            total=500, used=450, duration_days=30,
            traffic_action="reset", add_traffic=0,
        )
        self.assertEqual(plan.total, 500)
        self.assertEqual(plan.used, 0)
    def test_add_traffic_increases_total_without_reset(self):
        plan = build_renewal_plan(
            today=date(2026, 9, 18), current_expiry=date(2026, 9, 1),
            total=500, used=450, duration_days=30,
            traffic_action="add", add_traffic=200,
        )
        self.assertEqual(plan.total, 700)
        self.assertEqual(plan.used, 450)

    def test_unlimited_rejects_add_traffic(self):
        with self.assertRaises(ValueError):
            build_renewal_plan(
                today=date(2026, 9, 18), current_expiry=date(2026, 9, 1),
                total=0, used=0, duration_days=30,
                traffic_action="add", add_traffic=200,
            )


if __name__ == "__main__":
    unittest.main()

class RenewalLimitTests(unittest.TestCase):
    def test_preserve_rejects_exhausted_finite_plan(self):
        with self.assertRaises(ValueError):
            build_renewal_plan(
                today=date(2026, 9, 18), current_expiry=date(2026, 9, 1),
                total=500, used=500, duration_days=30,
                traffic_action="preserve", add_traffic=0,
            )


class UnlimitedResetTests(unittest.TestCase):
    def test_unlimited_reset_renews_30_days_from_today(self):
        self.assertEqual(
            unlimited_reset_expiry(total=0, today=date(2026, 9, 18)),
            date(2026, 10, 18),
        )

    def test_finite_reset_does_not_change_expiry(self):
        self.assertIsNone(
            unlimited_reset_expiry(total=50 * 1024**3, today=date(2026, 9, 18))
        )
