from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InlineUserQuickEditContractTests(unittest.TestCase):
    def test_inline_editor_component_and_controls_exist(self):
        path = ROOT / "frontend/src/components/InlineUserQuickEdit.jsx"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        for marker in (
            "quick-edit-traffic",
            "quick-edit-expiry",
            "quick-edit-device-limit",
            "quick-edit-active",
            "quick-edit-node",
            "quick-edit-reset-usage",
            "quick-edit-apply",
            "quick-edit-cancel",
        ):
            self.assertIn(marker, text)
        self.assertIn("readOnly", text)
        self.assertIn("Username rename", text)

    def test_user_table_mounts_inline_editor(self):
        text = (ROOT / "frontend/src/components/UserTable.jsx").read_text(encoding="utf-8")
        self.assertIn("InlineUserQuickEdit", text)
        self.assertIn("expandedUserUuid", text)
        self.assertIn("onQuickSave", text)

    def test_user_management_fetches_nodes_and_saves_quick_edit(self):
        text = (ROOT / "frontend/src/pages/UserManagement.jsx").read_text(encoding="utf-8")
        self.assertIn("fetchNodes", text)
        self.assertIn("handleQuickSave", text)
        self.assertIn("/nodes/", text)
        self.assertIn("/nodes`", text)

    def test_user_output_exposes_node_ids(self):
        output = (ROOT / "backend/schema/output.py").read_text(encoding="utf-8")
        users = (ROOT / "backend/routers/users.py").read_text(encoding="utf-8")
        self.assertIn("node_ids: list[int]", output)
        self.assertIn("UserNode", users)
        self.assertIn("item.node_ids", users)

    def test_assignment_endpoint_is_present(self):
        users = (ROOT / "backend/routers/users.py").read_text(encoding="utf-8")
        self.assertIn('@router.put("/{uuid}/nodes"', users)
        self.assertIn("replace_user_node_assignments", users)

    def test_status_sync_is_assignment_aware(self):
        users = (ROOT / "backend/routers/users.py").read_text(encoding="utf-8")
        start = users.index('@router.put("/{uuid}/status"')
        section = users[start:start + 1200]
        self.assertIn("change_user_status_on_assigned_nodes", section)
        self.assertNotIn("change_user_status_on_all_nodes", section)

    def test_safe_username_rename_is_tracked_separately(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        backlog = (ROOT / "docs/FEATURE-BACKLOG.md").read_text(encoding="utf-8")
        self.assertIn("PVN-022", agents)
        self.assertIn("safe multi-node username rename", agents.lower())
        self.assertIn("PVN-022", backlog)


if __name__ == "__main__":
    unittest.main()
