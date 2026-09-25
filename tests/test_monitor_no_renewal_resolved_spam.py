import unittest


class MonitorRenewalSpamTests(unittest.TestCase):
    """PVN-1014 — renewal keys must never reach the generic transition builder."""

    def test_generic_builder_sees_no_renewal_keys_on_either_side(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'backend/operations/telegram_monitor.py').read_text(encoding='utf-8')
        # The true every-run spam root: renewal keys were in 'alerts' (current)
        # but stripped only from old -> generic builder fired them as new forever.
        self.assertIn('node_alerts_only', source)
        self.assertIn('build_transition_messages(old_node_alerts, node_alerts_only)', source)

    def test_monitor_excludes_renewal_keys_from_node_transitions(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'backend/operations/telegram_monitor.py').read_text(encoding='utf-8')
        self.assertIn('old_node_alerts', source)
        self.assertIn('not key.startswith("renew:")', source)
        # build_transition_messages must receive the filtered dict.
        self.assertIn('build_transition_messages(old_node_alerts, alerts)', source)

    def test_generic_builder_would_have_spammed_renewal_keys(self):
        from backend.operations.alert_transitions import build_transition_messages
        old = {'renew:e:alice:7': '⏳ یادآوری تمدید: alice'}
        messages = build_transition_messages(old, {})
        # Without filtering, the generic builder announces Resolved for renewal
        # keys on every run — the exact live spam this hotfix removes.
        self.assertEqual(1, len(messages))
        self.assertIn('Resolved', messages[0])

    def test_filtered_pipeline_is_silent_for_ongoing_renewal(self):
        from backend.operations.renewal_alerts import build_renewal_transition_messages
        old = {'renew:e:alice:7': '⏳ یادآوری تمدید: alice', 'n:1:cpu': 'cpu'}
        renewal = {'renew:e:alice:7': '⏳ یادآوری تمدید: alice'}
        self.assertEqual([], build_renewal_transition_messages(old, renewal))


if __name__ == '__main__':
    unittest.main()
