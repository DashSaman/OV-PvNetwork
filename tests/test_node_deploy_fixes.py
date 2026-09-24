from pathlib import Path
from unittest.mock import patch

import unittest

ROOT = Path(__file__).resolve().parents[1]


class PanelSourceAutodetectTests(unittest.TestCase):
    """PVN-1008 — node-side allowlist source fixes."""

    def _script(self, panel_ip):
        from backend.node.deploy import _stage_script
        with patch("backend.node.deploy._domain_payload", return_value="Zm9v"):
            return _stage_script(9090, 1194, "udp", "key", panel_ip)

    def test_mode_classifier(self):
        from backend.node.deploy import _panel_firewall_mode
        self.assertEqual(("explicit", "203.0.113.5"), _panel_firewall_mode("203.0.113.5"))
        self.assertEqual(("explicit", "2001:db8::1"), _panel_firewall_mode("2001:db8::1"))
        self.assertEqual(("auto", ""), _panel_firewall_mode(None))
        self.assertEqual(("auto", ""), _panel_firewall_mode(""))
        # A hostname (panel behind a proxy/CDN) must degrade to auto, not crash.
        self.assertEqual(("auto", ""), _panel_firewall_mode("panel.example.com"))

    def test_auto_mode_derives_source_from_ssh_session(self):
        script = self._script(None)
        self.assertIn("PVNETWORK_PANEL_SOURCE_AUTODETECT_V1", script)
        self.assertIn('${SSH_CLIENT%% *}', script)
        self.assertIn('${SSH_CONNECTION%% *}', script)
        self.assertIn('PANEL_SOURCE_IP_UNRESOLVED', script)

    def test_hostname_panel_ip_no_longer_crashes_stage_script(self):
        # Before PVN-1008 this input raised ValueError in deploy_node.
        script = self._script("panel.example.com")
        self.assertIn('"auto"', script)

    def test_explicit_ip_is_embedded_literal(self):
        script = self._script("203.0.113.5")
        self.assertIn('"explicit"', script)
        self.assertIn('PANEL_SOURCE_IP="203.0.113.5"', script)

    def test_firewall_rules_use_position_one_and_quoted_source(self):
        script = self._script("203.0.113.5")
        # Position-2 insertion fails on servers with fewer existing rules.
        self.assertNotIn("-I INPUT 2", script)
        self.assertIn('-s "$PANEL_SOURCE_IP"', script)
        # Allow rules must be guarded by -C checks and DROP appended at the end.
        self.assertIn("iptables -C INPUT -p tcp -s", script)
        self.assertIn("iptables -A INPUT -p tcp --dport 9090 -j DROP", script)

    def test_ipv6_panel_gets_ip6tables_allow_branch(self):
        script = self._script("2001:db8::1")
        self.assertIn('ip6tables -C INPUT -p tcp -s "$PANEL_SOURCE_IP"', script)
        # The old blanket IPv6 DROP (which locked out IPv6 panels) is gone.
        self.assertNotIn("if command -v ip6tables", script)

    def test_deploy_node_signature_accepts_none_panel_ip(self):
        import inspect
        from backend.node.deploy import deploy_node
        self.assertIs(inspect.signature(deploy_node).parameters["panel_ip"].default, None)

    def test_deploy_schema_makes_panel_ip_optional(self):
        source = (ROOT / "backend/routers/node.py").read_text(encoding="utf-8")
        self.assertIn("panel_ip: Optional[str] = Field(default=None", source)
        self.assertIn("auto-detection from the", source)

    def test_deploy_verify_failure_has_actionable_message(self):
        source = (ROOT / "backend/routers/node.py").read_text(encoding="utf-8")
        self.assertIn("the panel could not reach the node API", source)

    def test_add_node_modal_panel_ip_optional_with_help(self):
        source = (ROOT / "frontend/src/components/AddNodeModal.jsx").read_text(encoding="utf-8")
        self.assertNotIn("window.location.hostname || ''", source)
        self.assertIn("addNodePanelIpPlaceholder", source)
        self.assertIn("addNodePanelIpHelp", source)
        self.assertIn("panel_ip.trim() ? formData.panel_ip.trim() : null", source)


if __name__ == "__main__":
    unittest.main()
