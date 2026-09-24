import os
import unittest
from datetime import date
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "test-hash")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-characters-long")

from backend.db.models import (
    Base,
    Node,
    NodeRouterOpenVpnConfig,
    RouterOpenVpnCredential,
    User,
    UserNode,
)


class RouterOpenVpnUserLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(
            uuid="11111111-2222-3333-4444-555555555555",
            name="alice",
            total=0,
            used=0,
            expiry_date=date(2030, 1, 1),
            is_active=True,
            owner="owner",
            device_limit=1,
        )
        self.node = Node(
            id=1, name="de1", address="192.0.2.10",
            tunnel_address="192.0.2.10", protocol="udp", ovpn_port=1194,
            port=9090, key="node-key", status=True,
        )
        self.db.add_all([
            self.user,
            self.node,
            UserNode(user_uuid=self.user.uuid, node_id=1),
            NodeRouterOpenVpnConfig(
                node_id=1, enabled=True, port=1195, protocol="tcp",
                subnet="10.9.0.0/24", capability_version="1",
            ),
        ])
        self.db.commit()
        self.actor = {"type": "main_admin", "username": "root"}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _healthy_client(self, mock_client):
        inst = mock_client.return_value
        inst.router_openvpn_status.return_value = {
            "ok": True, "capable": True, "upgrade_required": False,
            "data": {"enabled": True, "healthy": True, "version": "1"},
        }
        inst.router_openvpn_set_credential.return_value = {"ok": True, "data": {"ok": True}}
        return inst

    async def test_rotate_requires_active_explicit_assignment_and_healthy_listener(self):
        from backend.routers.router_openvpn import rotate_user_router_openvpn_credential

        self.db.query(UserNode).delete()
        self.db.commit()
        with self.assertRaises(HTTPException) as unassigned:
            await rotate_user_router_openvpn_credential(
                self.user.uuid, 1, db=self.db, actor=self.actor
            )
        self.assertEqual(unassigned.exception.status_code, 409)

        self.db.add(UserNode(user_uuid=self.user.uuid, node_id=1))
        self.user.is_active = False
        self.db.commit()
        with self.assertRaises(HTTPException) as inactive:
            await rotate_user_router_openvpn_credential(
                self.user.uuid, 1, db=self.db, actor=self.actor
            )
        self.assertEqual(inactive.exception.status_code, 409)

        self.user.is_active = True
        config = self.db.get(NodeRouterOpenVpnConfig, 1)
        config.enabled = False
        self.db.commit()
        with self.assertRaises(HTTPException) as disabled:
            await rotate_user_router_openvpn_credential(
                self.user.uuid, 1, db=self.db, actor=self.actor
            )
        self.assertEqual(disabled.exception.status_code, 409)

    async def test_rotate_pushes_cn_before_persist_and_returns_password_once(self):
        from backend.routers.router_openvpn import (
            get_user_router_openvpn_status,
            rotate_user_router_openvpn_credential,
        )
        with patch("backend.routers.router_openvpn._client") as client:
            inst = self._healthy_client(client)
            result = await rotate_user_router_openvpn_credential(
                self.user.uuid, 1, db=self.db, actor=self.actor
            )
        data = result["data"]
        self.assertEqual(data["common_name"], "alice-de1")
        self.assertGreaterEqual(len(data["password"]), 32)
        call = inst.router_openvpn_set_credential.call_args
        self.assertEqual(call.kwargs["cn"], "alice-de1")
        self.assertEqual(call.kwargs["username"], data["username"])
        self.assertNotEqual(call.kwargs["verifier"], data["password"])
        row = self.db.get(RouterOpenVpnCredential, (self.user.uuid, 1))
        self.assertTrue(row.enabled)
        self.assertNotIn(data["password"], row.password_hash)

        status = await get_user_router_openvpn_status(
            self.user.uuid, 1, db=self.db, actor=self.actor
        )
        # PVN-1012: the stored ciphertext is revealed to authenticated admins.
        self.assertTrue(status["data"]["password_available"])
        self.assertEqual(status["data"]["password"], data["password"])

    async def test_node_push_failure_leaves_no_central_credential(self):
        from backend.routers.router_openvpn import rotate_user_router_openvpn_credential
        with patch("backend.routers.router_openvpn._client") as client:
            inst = self._healthy_client(client)
            inst.router_openvpn_set_credential.return_value = {"ok": False, "data": {"error": "node failure"}}
            with self.assertRaises(HTTPException) as failure:
                await rotate_user_router_openvpn_credential(
                    self.user.uuid, 1, db=self.db, actor=self.actor
                )
        self.assertEqual(failure.exception.status_code, 502)
        self.assertIsNone(self.db.get(RouterOpenVpnCredential, (self.user.uuid, 1)))

    async def test_profile_uses_canonical_cn_and_contains_no_password(self):
        from fastapi.responses import Response
        from backend.routers.router_openvpn import (
            download_user_router_openvpn_profile,
            rotate_user_router_openvpn_credential,
        )
        with patch("backend.routers.router_openvpn._client") as client:
            inst = self._healthy_client(client)
            await rotate_user_router_openvpn_credential(
                self.user.uuid, 1, db=self.db, actor=self.actor
            )
            inst.router_openvpn_profile.return_value = Response(
                content=b"client\nauth-user-pass\n<cert>safe</cert>\n",
                media_type="application/x-openvpn-profile",
            )
            response = await download_user_router_openvpn_profile(
                self.user.uuid, 1, db=self.db, actor=self.actor
            )
        inst.router_openvpn_profile.assert_called_once_with("alice-de1")
        self.assertNotIn(b"password", response.body.lower())


    async def test_disabling_user_disables_existing_router_credential_best_effort(self):
        from backend.node.assignment import change_user_status_on_assigned_nodes
        self.db.add(RouterOpenVpnCredential(
            user_uuid=self.user.uuid, node_id=1, router_username="r_test_1",
            password_hash="scrypt$32768$8$1$x$y", enabled=True,
            created_at=1, updated_at=1, password_changed_at=1,
        ))
        self.db.commit()
        request = Mock()
        request.check_node.return_value = True
        request.change_user_status.return_value = True
        request.router_openvpn_set_credential.return_value = {"ok": True}
        with patch("backend.node.assignment._node_request", return_value=request):
            ok = await change_user_status_on_assigned_nodes(
                self.user.uuid, self.user.name, False, self.db
            )
        self.assertTrue(ok)
        self.assertFalse(self.db.query(User).filter(User.uuid == self.user.uuid).one().is_active)
        self.assertFalse(self.db.get(RouterOpenVpnCredential, (self.user.uuid, 1)).enabled)
        request.router_openvpn_set_credential.assert_called_once()
        self.assertFalse(request.router_openvpn_set_credential.call_args.kwargs["enabled"])

    async def test_assignment_removal_disables_router_credential_after_assignment_commit(self):
        from backend.node.assignment import replace_user_node_assignments
        node2 = Node(
            id=2, name="us1", address="192.0.2.11", tunnel_address="192.0.2.11",
            protocol="udp", ovpn_port=1194, port=9090, key="node-key-2", status=True,
        )
        self.db.add_all([
            node2, UserNode(user_uuid=self.user.uuid, node_id=2),
            RouterOpenVpnCredential(
                user_uuid=self.user.uuid, node_id=1, router_username="r_test_1",
                password_hash="scrypt$32768$8$1$x$y", enabled=True,
                created_at=1, updated_at=1, password_changed_at=1,
            ),
        ])
        self.db.commit()
        request = Mock()
        request.check_node.return_value = True
        request.change_user_status.return_value = True
        request.router_openvpn_set_credential.return_value = {"ok": True}
        with patch("backend.node.assignment._node_request", return_value=request):
            result = await replace_user_node_assignments(
                self.user.uuid, self.user.name, [2], self.db
            )
        self.assertEqual(result["removed_node_ids"], [1])
        self.assertEqual(result["router_cleanup_pending_node_ids"], [])
        self.assertIsNone(self.db.get(UserNode, (self.user.uuid, 1)))
        self.assertFalse(self.db.get(RouterOpenVpnCredential, (self.user.uuid, 1)).enabled)

    async def test_delete_revokes_router_credential_only_after_database_delete(self):
        from backend.routers.users import delete_user
        self.db.add(RouterOpenVpnCredential(
            user_uuid=self.user.uuid, node_id=1, router_username="r_test_1",
            password_hash="scrypt$32768$8$1$x$y", enabled=True,
            created_at=1, updated_at=1, password_changed_at=1,
        ))
        self.db.commit()
        observed = {}
        async def revoke(snapshot):
            observed["user_missing"] = self.db.get(User, self.user.uuid) is None
            observed["snapshot_count"] = len(snapshot)
            return {"all_ok": True, "revoked": [{"node_id": 1}], "failed": []}
        with patch("backend.routers.users.delete_user_on_all_nodes", return_value={"all_ok": True, "deleted": [], "failed": []}), \
             patch("backend.routers.users.revoke_router_credentials_snapshot", side_effect=revoke):
            result = await delete_user(
                self.user.uuid, db=self.db, user=self.actor
            )
        self.assertTrue(observed["user_missing"])
        self.assertEqual(observed["snapshot_count"], 1)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
