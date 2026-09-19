import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "test-hash")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-contract-tests")

from backend.node.requests import NodeRequests


class RouterOpenVpnNodeContractTests(unittest.TestCase):
    def _client(self):
        return NodeRequests(
            address="192.0.2.10",
            port=9090,
            api_key="test-key",
            tunnel_address="192.0.2.10",
            protocol="udp",
            ovpn_port=1194,
        )

    @patch("backend.node.requests.requests.request")
    def test_old_node_404_is_upgrade_required_not_health_failure(self, request):
        response = Mock(status_code=404, ok=False)
        response.json.return_value = {"detail": "Not Found"}
        request.return_value = response

        result = self._client().router_openvpn_status()

        self.assertEqual(
            result,
            {
                "ok": False,
                "capable": False,
                "upgrade_required": True,
                "status_code": 404,
                "msg": "Router OpenVPN capability is not installed",
                "data": None,
            },
        )

    @patch("backend.node.requests.requests.request")
    def test_router_methods_use_isolated_node_routes(self, request):
        response = Mock(status_code=200, ok=True, content=b"profile")
        response.json.return_value = {
            "success": True,
            "data": {"ok": True, "capable": True, "healthy": True},
        }
        request.return_value = response
        client = self._client()

        self.assertTrue(client.router_openvpn_status()["ok"])
        self.assertTrue(client.router_openvpn_preflight(1195, "tcp", "10.9.0.0/24")["ok"])
        self.assertTrue(client.router_openvpn_config(
            enabled=True, port=1195, protocol="tcp", subnet="10.9.0.0/24"
        )["ok"])
        self.assertTrue(client.router_openvpn_set_credential(
            cn="user-node", username="r_abc_1", verifier="scrypt$32768$8$1$x$y", enabled=True
        )["ok"])
        profile = client.router_openvpn_profile("user-node")
        self.assertIsNotNone(profile)

        called_urls = [call.args[1] for call in request.call_args_list]
        self.assertTrue(all("/sync/router-openvpn/" in url for url in called_urls))
        self.assertFalse(any("/sync/status" in url for url in called_urls))

    def test_fresh_node_stage_installs_capability_but_does_not_enable_listener(self):
        from backend.node.deploy import _stage_script

        script = _stage_script(9090, 1194, "udp", "key", "203.0.113.5")
        self.assertIn("pvnetwork-router-openvpn", script)
        self.assertIn("pvnetwork-router-auth", script)
        self.assertNotIn("systemctl start openvpn-server@pvnetwork-router", script)
        self.assertNotIn("systemctl enable openvpn-server@pvnetwork-router", script)

    def test_fleet_capability_install_is_explicit_and_idempotent(self):
        from backend.routers.fleet import router_capability_install_script

        script = router_capability_install_script("/opt/ov-node")
        self.assertIn("pvnetwork-router-openvpn", script)
        self.assertIn("pvnetwork-router-auth", script)
        self.assertIn("--router-only", script)
        self.assertNotIn("systemctl start openvpn-server@pvnetwork-router", script)

    def test_fleet_upgrade_installs_capability_before_node_restart_only(self):
        from backend.routers.fleet import build_upgrade_script

        script = build_upgrade_script()
        install_at = script.index("PVNETWORK_ROUTER_CAPABILITY_V1")
        restart_at = script.index("systemctl restart ov-node")
        self.assertLess(install_at, restart_at)
        self.assertNotIn("systemctl restart openvpn-server@server", script)
        self.assertNotIn("systemctl start openvpn-server@pvnetwork-router", script)


if __name__ == "__main__":
    unittest.main()
