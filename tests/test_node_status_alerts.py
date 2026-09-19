from pathlib import Path
import unittest

from backend.operations.alert_transitions import (
    build_node_status_alerts,
    build_transition_messages,
)


class NodeStatusAlertTests(unittest.TestCase):
    def test_offline_node_creates_down_alert_when_enabled(self):
        nodes = [{"id": 7, "name": "Demo-DE", "health": "offline"}]
        alerts = build_node_status_alerts(nodes, enabled=True)
        self.assertEqual(alerts, {"n:7:down": "🔴 Node DOWN: Demo-DE"})

    def test_offline_node_does_not_alert_when_disabled(self):
        nodes = [{"id": 7, "name": "Demo-DE", "health": "offline"}]
        self.assertEqual(build_node_status_alerts(nodes, enabled=False), {})

    def test_recovery_message_is_explicit_node_up(self):
        old = {"n:7:down": "🔴 Node DOWN: Demo-DE"}
        current = {}
        messages = build_transition_messages(old, current)
        self.assertEqual(messages, ["🟢 Node UP: Demo-DE"])

    def test_unchanged_down_state_does_not_repeat(self):
        old = {"n:7:down": "🔴 Node DOWN: Demo-DE"}
        current = {"n:7:down": "🔴 Node DOWN: Demo-DE"}
        self.assertEqual(build_transition_messages(old, current), [])

    def test_monitoring_ui_exposes_node_status_toggle(self):
        source = (Path(__file__).resolve().parents[1] / "frontend/src/pages/MonitoringSettings.jsx").read_text()
        self.assertIn("node_status_alerts", source)
        self.assertIn("nodeStatusAlerts", source)

    def test_migration_adds_enabled_by_default_toggle(self):
        source = (Path(__file__).resolve().parents[1] / "backend/alembic/versions/c2d3e4f5a6b7_node_status_telegram_alerts.py").read_text()
        self.assertIn("node_status_alerts", source)
        self.assertIn("server_default=sa.true()", source)


if __name__ == "__main__":
    unittest.main()
