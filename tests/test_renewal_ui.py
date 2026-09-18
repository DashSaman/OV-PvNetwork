import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RenewalUiSmokeTests(unittest.TestCase):
    def test_renew_modal_exists(self):
        path = ROOT / "frontend/src/components/RenewUserModal.jsx"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn('/renew', text)
        self.assertIn('traffic_action', text)

    def test_user_table_exposes_renew_action(self):
        text = (ROOT / "frontend/src/components/UserTable.jsx").read_text(encoding="utf-8")
        self.assertIn('onRenew', text)
        self.assertIn("renewButton", text)


if __name__ == "__main__":
    unittest.main()
