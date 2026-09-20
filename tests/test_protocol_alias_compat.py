import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class ProtocolAliasCompatibilityTests(unittest.TestCase):
    def test_api_tokens_write_pvnetwork_prefix_and_dual_read_legacy_prefix(self):
        security = text("backend/routers/security.py")
        middleware = text("backend/security_middleware.py")
        audit = text("backend/audit.py")

        self.assertIn("pvn_", security)
        self.assertNotIn("raw='ovp_'", security)
        for source in (middleware, audit):
            self.assertIn("pvn_", source)
            self.assertIn("ovp_", source)


    def test_node_key_resolver_dual_reads_and_rejects_conflict(self):
        compat_path = ROOT / "backend/protocol_compat.py"
        self.assertTrue(compat_path.exists(), "protocol compatibility helper is missing")

        from backend.protocol_compat import resolve_node_key
        from fastapi import HTTPException

        self.assertEqual(resolve_node_key("new-key", None), "new-key")
        self.assertEqual(resolve_node_key(None, "old-key"), "old-key")
        self.assertEqual(resolve_node_key("same", "same"), "same")
        with self.assertRaises(HTTPException) as raised:
            resolve_node_key("new-key", "old-key")
        self.assertEqual(raised.exception.status_code, 400)
        with self.assertRaises(HTTPException) as missing:
            resolve_node_key(None, None)
        self.assertEqual(missing.exception.status_code, 422)


    def test_all_node_integrations_use_shared_dual_header_dependency(self):
        anyconnect = text("backend/routers/anyconnect.py")
        domain = text("backend/routers/domain_activity.py")
        mirza = text("backend/routers/mirza.py")

        self.assertIn("from backend.protocol_compat import node_key_header", anyconnect)
        self.assertIn("from backend.protocol_compat import node_key_header", domain)
        self.assertIn("from backend.protocol_compat import node_key_header", mirza)
        self.assertIn("node_key: str = Depends(node_key_header)", anyconnect)
        self.assertIn("node_key: str = Depends(node_key_header)", domain)
        self.assertGreaterEqual(mirza.count("node_key: str = _SessionDepends(node_key_header)"), 5)
        self.assertNotIn('alias="X-OV-Node-Key"', anyconnect)
        self.assertNotIn('alias="X-OV-Node-Key"', domain)
        self.assertNotIn('alias="X-OV-Node-Key"', mirza)


    def test_node_upgrade_injects_pvnetwork_owned_helper_aliases(self):
        import base64
        import re

        deploy = text("backend/node/deploy.py")
        match = re.search(
            r"echo '([A-Za-z0-9+/=]+)' \| base64 -d >/tmp/ov-node-compat-patch\.py",
            deploy,
        )
        self.assertIsNotNone(match)
        compat_patch = base64.b64decode(match.group(1)).decode("utf-8")

        self.assertIn("def _pvnetwork_dashboard_default_interface", compat_patch)
        self.assertIn("def _pvnetwork_dashboard_network_snapshot", compat_patch)
        self.assertIn("def _pvnetwork_openvpn_online_snapshot", compat_patch)
        self.assertIn("_ov_dashboard_network_snapshot", compat_patch)
        self.assertIn("_pvnetwork_dashboard_network_snapshot", compat_patch)
        self.assertNotIn("def _ov_dashboard_network_snapshot", compat_patch)
        self.assertNotIn("def _ov_openvpn_online_snapshot", compat_patch)

        self.assertIn("grep -q '_pvnetwork_dashboard_network_snapshot'", deploy)
        self.assertIn("status.update(_pvnetwork_dashboard_network_snapshot())", deploy)
        self.assertIn("status.update(_pvnetwork_openvpn_online_snapshot())", deploy)


if __name__ == "__main__":
    unittest.main()
