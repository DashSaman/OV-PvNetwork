import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.operations.live_presence import merge_presence_snapshot
from backend.node.health import _probe_node


class RouterOpenVpnPresenceTests(unittest.TestCase):
    def test_same_cn_on_normal_and_router_listener_counts_once(self):
        result = merge_presence_snapshot(
            users=[("u1", "alice")],
            central_counts={},
            node_clients={1: ("de1", {"alice-de1"})},
        )
        self.assertEqual(result["online_users"], 1)
        self.assertEqual(result["counts_by_uuid"], {"u1": 1})

    def test_node_patch_exposes_router_snapshot_and_common_names(self):
        source = (Path(__file__).resolve().parents[1] / "scripts/node_patch.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('status["router_openvpn"]', source)
        self.assertIn("online_common_names", source)
        self.assertIn("/var/log/openvpn-router-status.log", source)


class RouterOpenVpnHealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_node_health_exposes_raw_router_listener_metrics(self):
        node = type("Node", (), {
            "id": 1, "name": "de1", "address": "192.0.2.10", "port": 9090,
            "key": "k", "tunnel_address": "192.0.2.10", "protocol": "udp",
            "ovpn_port": 1194, "status": True, "drain": False, "weight": 100,
        })()
        info = {
            "status": "running", "cpu_usage": 1, "memory_usage": 2,
            "online_count": 1, "online_sessions": 1,
            "router_openvpn": {
                "capable": True, "enabled": True, "healthy": True,
                "online_clients": 2, "port": 1195, "protocol": "tcp",
            },
        }
        with patch("backend.node.health.NodeRequests") as requests:
            requests.return_value.get_node_info.return_value = info
            result = await _probe_node(node, {})
        self.assertEqual(result["router_openvpn"]["online_clients"], 2)
        self.assertEqual(result["reported_online_sessions"], 1)


if __name__ == "__main__":
    unittest.main()


class RouterOpenVpnDirectFallbackTests(unittest.TestCase):
    def test_direct_presence_unions_normal_and_router_common_names(self):
        from backend.operations.live_presence import _read_node_clients
        spec = {
            "address": "192.0.2.10", "port": 9090, "key": "k",
            "tunnel_address": "192.0.2.10", "protocol": "udp",
            "ovpn_port": 1194,
        }
        with patch("backend.operations.live_presence.NodeRequests") as requests:
            inst = requests.return_value
            inst.get_users_usage.return_value = {"users": {"alice-de1": 1}}
            inst.router_openvpn_status.return_value = {
                "ok": True,
                "data": {"online_common_names": ["alice-de1", "bob-de1"]},
            }
            clients = _read_node_clients(spec)
        self.assertEqual(clients, {"alice-de1", "bob-de1"})

    def test_successful_empty_usage_is_a_fresh_empty_snapshot(self):
        from backend.operations.live_presence import _read_node_clients
        spec = {
            "address": "192.0.2.10", "port": 9090, "key": "k",
            "tunnel_address": "192.0.2.10", "protocol": "udp",
            "ovpn_port": 1194,
        }
        with patch("backend.operations.live_presence.NodeRequests") as requests:
            inst = requests.return_value
            inst.get_users_usage.return_value = None
            inst.router_openvpn_status.return_value = {"ok": False, "data": None}
            clients = _read_node_clients(spec)
        self.assertEqual(clients, set())

    def test_usage_transport_failure_remains_unknown(self):
        from backend.operations.live_presence import _read_node_clients
        spec = {
            "address": "192.0.2.10", "port": 9090, "key": "k",
            "tunnel_address": "192.0.2.10", "protocol": "udp",
            "ovpn_port": 1194,
        }
        with patch("backend.operations.live_presence.NodeRequests") as requests:
            inst = requests.return_value
            inst.get_users_usage.return_value = False
            inst.router_openvpn_status.return_value = {"ok": False, "data": None}
            clients = _read_node_clients(spec)
        self.assertIsNone(clients)
