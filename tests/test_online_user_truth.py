import os
os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD", "ci-password-not-production")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

import unittest
from pathlib import Path

from backend.operations.live_presence import (
    client_username,
    merge_presence_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


class OnlineUserTruthTests(unittest.TestCase):
    def test_client_username_strips_only_exact_node_suffix(self):
        self.assertEqual(
            client_username("user-with-hyphen-USA-East", "USA-East"),
            "user-with-hyphen",
        )
        self.assertIsNone(client_username("user-USA", "USA-East"))

    def test_direct_node_fallback_adds_missing_central_user(self):
        result = merge_presence_snapshot(
            users=[("uuid-a", "alice"), ("uuid-b", "bob")],
            central_counts={"uuid-a": 1},
            node_clients={4: ("USA", {"bob-USA"})},
        )
        self.assertEqual(result["counts_by_uuid"], {"uuid-a": 1, "uuid-b": 1})
        self.assertEqual(result["online_users"], 2)
        self.assertEqual(result["direct_fallback_users"], 1)

    def test_same_user_on_multiple_nodes_is_one_online_user(self):
        result = merge_presence_snapshot(
            users=[("uuid-a", "alice")],
            central_counts={},
            node_clients={
                3: ("Finland", {"alice-Finland"}),
                5: ("Germany", {"alice-Germany"}),
            },
        )
        self.assertEqual(result["online_users"], 1)
        self.assertEqual(result["counts_by_uuid"]["uuid-a"], 2)

    def test_central_session_count_is_not_double_counted_by_direct_presence(self):
        result = merge_presence_snapshot(
            users=[("uuid-a", "alice")],
            central_counts={"uuid-a": 2},
            node_clients={3: ("Finland", {"alice-Finland"})},
        )
        self.assertEqual(result["counts_by_uuid"]["uuid-a"], 2)
        self.assertEqual(result["online_users"], 1)
        self.assertEqual(result["direct_fallback_users"], 0)

    def test_unknown_node_client_is_not_counted_as_panel_user(self):
        result = merge_presence_snapshot(
            users=[("uuid-a", "alice")],
            central_counts={},
            node_clients={4: ("USA", {"unknown-USA"})},
        )
        self.assertEqual(result["online_users"], 0)
        self.assertEqual(result["unmapped_clients"], 1)

    def test_wiring_uses_shared_presence_without_writing_active_sessions(self):
        users_router = (ROOT / "backend/routers/users.py").read_text()
        dashboard_router = (ROOT / "backend/routers/setting.py").read_text()
        dashboard = (ROOT / "frontend/src/pages/ServerStats.jsx").read_text()
        live_presence = (ROOT / "backend/operations/live_presence.py").read_text()
        requests_source = (ROOT / "backend/node/requests.py").read_text()

        self.assertIn("get_display_live_presence", users_router)
        self.assertIn("await get_display_live_presence", users_router)
        self.assertIn("get_display_live_presence", dashboard_router)
        self.assertIn('"presence": presence', dashboard_router)
        self.assertIn("payload.presence", dashboard)
        self.assertIn("presence.online_users", dashboard)
        self.assertNotIn("db.add(ActiveSession", live_presence)
        self.assertNotIn("db.merge(ActiveSession", live_presence)
        self.assertIn("def get_users_usage(self, timeout=", requests_source)


if __name__ == "__main__":
    unittest.main()
