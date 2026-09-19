import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "test-hash")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-characters-long")

from backend.db.models import Base, Node, NodeRouterOpenVpnConfig


class RouterOpenVpnApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.node = Node(
            id=1, name="node1", address="192.0.2.10",
            tunnel_address="192.0.2.10", protocol="udp", ovpn_port=1194,
            port=9090, key="secret-node-key", status=True,
        )
        self.db.add(self.node)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_get_allows_admin_but_never_exposes_node_key(self):
        from backend.routers.router_openvpn import get_node_router_openvpn
        with patch("backend.routers.router_openvpn._client") as client:
            client.return_value.router_openvpn_status.return_value = {
                "ok": False, "capable": False, "upgrade_required": True,
                "status_code": 404, "msg": "missing", "data": None,
            }
            result = await get_node_router_openvpn(
                1, db=self.db, actor={"type": "admin", "username": "reseller"}
            )
        data = result["data"]
        self.assertTrue(data["upgrade_required"])
        self.assertFalse(data["capable"])
        self.assertNotIn("key", data)
        self.assertNotIn("address", data)

    async def test_missing_node_is_404(self):
        from fastapi import HTTPException
        from backend.routers.router_openvpn import get_node_router_openvpn
        with self.assertRaises(HTTPException) as ctx:
            await get_node_router_openvpn(
                999, db=self.db, actor={"type": "main_admin", "username": "root"}
            )
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_preflight_is_main_admin_only_and_failure_does_not_mutate_db(self):
        from fastapi import HTTPException
        from backend.routers.router_openvpn import RouterOpenVpnConfigInput, preflight_node_router_openvpn
        req = RouterOpenVpnConfigInput(port=1195, protocol="tcp", subnet="10.9.0.0/24")
        with self.assertRaises(HTTPException) as forbidden:
            await preflight_node_router_openvpn(
                1, req, db=self.db, actor={"type": "admin", "username": "reseller"}
            )
        self.assertEqual(forbidden.exception.status_code, 403)
        with patch("backend.routers.router_openvpn._client") as client:
            client.return_value.router_openvpn_preflight.return_value = {
                "ok": False, "capable": True, "upgrade_required": False,
                "status_code": 200, "msg": "PORT_IN_USE", "data": {"error": "PORT_IN_USE"},
            }
            with self.assertRaises(HTTPException) as conflict:
                await preflight_node_router_openvpn(
                    1, req, db=self.db,
                    actor={"type": "main_admin", "username": "root"},
                )
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertIsNone(self.db.get(NodeRouterOpenVpnConfig, 1))

    async def test_enable_commits_only_after_healthy_node_confirmation(self):
        from backend.routers.router_openvpn import RouterOpenVpnConfigInput, configure_node_router_openvpn
        req = RouterOpenVpnConfigInput(enabled=True, port=1195, protocol="tcp", subnet="10.9.0.0/24")
        with patch("backend.routers.router_openvpn._client") as client:
            inst = client.return_value
            inst.router_openvpn_preflight.return_value = {"ok": True, "capable": True, "data": {"ok": True}}
            inst.router_openvpn_config.return_value = {"ok": True, "capable": True, "data": {"ok": True}}
            inst.router_openvpn_status.return_value = {
                "ok": True, "capable": True, "upgrade_required": False,
                "data": {"ok": True, "healthy": True, "enabled": True, "version": "1"},
            }
            result = await configure_node_router_openvpn(
                1, req, db=self.db, actor={"type": "main_admin", "username": "root"}
            )
        row = self.db.get(NodeRouterOpenVpnConfig, 1)
        self.assertTrue(row.enabled)
        self.assertEqual(row.port, 1195)
        self.assertTrue(result["data"]["healthy"])

    async def test_node_failure_rolls_back_metadata_and_compensates_secondary(self):
        from fastapi import HTTPException
        from backend.routers.router_openvpn import RouterOpenVpnConfigInput, configure_node_router_openvpn
        req = RouterOpenVpnConfigInput(enabled=True, port=1195, protocol="tcp", subnet="10.9.0.0/24")
        with patch("backend.routers.router_openvpn._client") as client:
            inst = client.return_value
            inst.router_openvpn_preflight.return_value = {"ok": True, "capable": True, "data": {"ok": True}}
            inst.router_openvpn_config.return_value = {"ok": True, "capable": True, "data": {"ok": True}}
            inst.router_openvpn_status.return_value = {
                "ok": False, "capable": True, "upgrade_required": False,
                "data": {"ok": False, "healthy": False, "enabled": True},
            }
            with self.assertRaises(HTTPException) as failure:
                await configure_node_router_openvpn(
                    1, req, db=self.db, actor={"type": "main_admin", "username": "root"}
                )
        self.assertEqual(failure.exception.status_code, 502)
        self.assertIsNone(self.db.get(NodeRouterOpenVpnConfig, 1))
        self.assertTrue(any(call.kwargs.get("enabled") is False for call in inst.router_openvpn_config.call_args_list))

    async def test_repeated_healthy_enable_does_not_mutate_listener_twice(self):
        from backend.routers.router_openvpn import RouterOpenVpnConfigInput, configure_node_router_openvpn
        req = RouterOpenVpnConfigInput(enabled=True, port=1195, protocol="tcp", subnet="10.9.0.0/24")
        with patch("backend.routers.router_openvpn._client") as client:
            inst = client.return_value
            inst.router_openvpn_preflight.return_value = {"ok": True, "capable": True, "data": {"ok": True}}
            inst.router_openvpn_config.return_value = {"ok": True, "capable": True, "data": {"ok": True}}
            inst.router_openvpn_status.return_value = {
                "ok": True, "capable": True, "upgrade_required": False,
                "data": {"ok": True, "healthy": True, "enabled": True, "version": "1"},
            }
            await configure_node_router_openvpn(1, req, db=self.db, actor={"type": "main_admin", "username": "root"})
            await configure_node_router_openvpn(1, req, db=self.db, actor={"type": "main_admin", "username": "root"})
        self.assertEqual(inst.router_openvpn_config.call_count, 1)

    async def test_disable_is_idempotent(self):
        from backend.routers.router_openvpn import RouterOpenVpnConfigInput, configure_node_router_openvpn
        self.db.add(NodeRouterOpenVpnConfig(node_id=1, enabled=True, port=1195, protocol="tcp", subnet="10.9.0.0/24"))
        self.db.commit()
        req = RouterOpenVpnConfigInput(enabled=False, port=1195, protocol="tcp", subnet="10.9.0.0/24")
        with patch("backend.routers.router_openvpn._client") as client:
            client.return_value.router_openvpn_config.return_value = {"ok": True, "capable": True, "data": {"ok": True, "enabled": False}}
            await configure_node_router_openvpn(1, req, db=self.db, actor={"type": "main_admin", "username": "root"})
            await configure_node_router_openvpn(1, req, db=self.db, actor={"type": "main_admin", "username": "root"})
        self.assertFalse(self.db.get(NodeRouterOpenVpnConfig, 1).enabled)
        self.assertEqual(client.return_value.router_openvpn_config.call_count, 1)


if __name__ == "__main__":
    unittest.main()

class RouterOpenVpnRegistrationTests(unittest.TestCase):
    def test_app_registers_router_openvpn_api_without_secret_route(self):
        source = (Path(__file__).resolve().parents[1] / "backend/app.py").read_text(encoding="utf-8")
        self.assertIn("router as router_openvpn_router", source)
        self.assertIn('api.include_router(prefix="/api", router=router_openvpn_router)', source)
        router_source = (Path(__file__).resolve().parents[1] / "backend/routers/router_openvpn.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/nodes/{node_id}")', router_source)
        self.assertIn('@router.post("/nodes/{node_id}/preflight")', router_source)
        self.assertNotIn("node-key", router_source)
