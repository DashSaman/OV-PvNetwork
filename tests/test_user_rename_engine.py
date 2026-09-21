import asyncio
import json
import unittest
import importlib.util
from contextlib import nullcontext
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.engine import Base
from backend.db.models import (
    ActiveSession, AnyConnectCredential, Node, RouterOpenVpnCredential,
    User, UserNode, UserNodeUsage,
)
from backend.user_rename.repository import create_rename_job

try:
    from backend.user_rename.engine import (
        RenameStageError,
        preflight_job,
        stage_new_identities,
        disable_old_identities,
        rollback_precommit,
    )
except ModuleNotFoundError:
    class RenameStageError(RuntimeError): pass
    async def _missing(*a, **k): raise AssertionError("rename engine missing")
    preflight_job = stage_new_identities = disable_old_identities = rollback_precommit = _missing


class FakeNodeClient:
    def __init__(self, node_name):
        self.node_name = node_name
        self.create_ok = True
        self.disable_ok = True
        self.delete_ok = True
        self.reachable = True
        self.created = []
        self.deleted = []
        self.status_calls = []
        self.identities = set()
        self.connected = set()

    def check_node(self):
        return self.reachable

    def create_user(self, name):
        if not self.create_ok:
            return False
        self.created.append(name); self.identities.add(name); return True

    def delete_user(self, name):
        self.deleted.append(name)
        if self.delete_ok:
            self.identities.discard(name); self.connected.discard(name); return True
        return False

    def change_user_status(self, name, status):
        self.status_calls.append((name, bool(status)))
        if not self.disable_ok and not status:
            return False
        if status: self.identities.add(name)
        else: self.connected.discard(name)
        return True

    def get_user_identity(self, name):
        return {
            "exists": name in self.identities,
            "valid_certificate": name in self.identities,
            "profile_exists": name in self.identities,
            "ccd_enabled": name in self.identities,
            "connected": name in self.connected,
            "client_name": name,
            "capability_version": "pvn-user-identity-v1",
        }

    def download_ovpn_client(self, name):
        return object() if name in self.identities else None


class UserRenameStageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.user = User(name="old", uuid="u-1", owner="root", total=0, used=77, expiry_date=date.today(), is_active=True, device_limit=1)
        self.db.add(self.user)
        self.nodes = []
        self.fake = {}
        for i, name in ((1, "A"), (2, "B"), (3, "C")):
            node = Node(id=i, name=name, address=f"10.0.0.{i}", tunnel_address=None, protocol="tcp", ovpn_port=1194, port=8000+i, key="k"*16, status=True, drain=False, maintenance=False, weight=100, health_score=100)
            self.db.add(node); self.nodes.append(node); self.db.add(UserNode(user_uuid="u-1", node_id=i)); self.fake[i] = FakeNodeClient(name)
            self.fake[i].identities.add(f"old-{name}")
        self.db.commit()
        self.job = create_rename_job(self.db, user_uuid="u-1", old_name="old", new_name="new", actor="root", actor_type="main_admin")
        self.db.commit()

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def node_request(self, node):
        return self.fake[int(node.id)]

    def patch_client(self):
        if importlib.util.find_spec("backend.user_rename.engine") is None:
            return nullcontext()
        return patch("backend.user_rename.engine._node_request", side_effect=self.node_request)

    async def test_preflight_snapshots_ordered_nodes_and_immutable_user_state(self):
        with self.patch_client():
            result = await preflight_job(self.job, self.db)
        self.assertEqual([n["id"] for n in result["nodes"]], [1,2,3])
        self.assertTrue(result["original_active"])
        self.assertEqual(result["user_uuid"], "u-1")
        self.assertEqual(result["used"], 77)

    async def test_staging_failure_deletes_every_new_identity_created_by_job(self):
        self.fake[3].create_ok = False
        with self.patch_client():
            await preflight_job(self.job, self.db)
            with self.assertRaises(RenameStageError):
                await stage_new_identities(self.job, self.db)
        self.assertEqual(self.fake[1].deleted, ["new-A"])
        self.assertEqual(self.fake[2].deleted, ["new-B"])
        self.assertEqual(self.user.name, "old")

    async def test_inactive_user_stages_new_identities_inactive(self):
        self.user.is_active = False; self.db.commit()
        with self.patch_client():
            await preflight_job(self.job, self.db)
            await stage_new_identities(self.job, self.db)
        for i, name in ((1,"A"),(2,"B"),(3,"C")):
            self.assertIn((f"new-{name}", False), self.fake[i].status_calls)

    async def test_disable_failure_restores_old_and_removes_staged_new(self):
        self.fake[2].disable_ok = False
        with self.patch_client():
            await preflight_job(self.job, self.db)
            await stage_new_identities(self.job, self.db)
            with self.assertRaises(RenameStageError):
                await disable_old_identities(self.job, self.db)
        self.assertIn(("old-A", True), self.fake[1].status_calls)
        for i, name in ((1,"A"),(2,"B"),(3,"C")):
            self.assertIn(f"new-{name}", self.fake[i].deleted)
        self.assertEqual(self.user.name, "old")


class UserRenameCutoverTests(UserRenameStageTests):
    def add_uuid_bound_state(self):
        self.db.add_all([
            UserNodeUsage(user_uuid="u-1", node_id=1, last_usage=1234),
            AnyConnectCredential(user_uuid="u-1", password_hash="hash-keep", password_ciphertext=None, enabled=True, created_at=1, updated_at=2, password_changed_at=3),
            RouterOpenVpnCredential(user_uuid="u-1", node_id=1, router_username="router_fixed", password_hash="router-hash", enabled=True, created_at=1, updated_at=2, password_changed_at=3),
            ActiveSession(session_id="s-old", user_uuid="u-1", node_id=1, common_name="old-A", remote_addr="198.51.100.1", acquired_at=1, last_seen=2),
        ])
        self.db.commit()

    async def test_atomic_cutover_preserves_uuid_keyed_state_and_removes_old_session(self):
        import backend.user_rename.engine as impl
        self.assertTrue(hasattr(impl, "commit_central_rename"), "commit_central_rename missing")
        self.add_uuid_bound_state()
        before = {
            "uuid": self.user.uuid, "owner": self.user.owner, "total": self.user.total,
            "used": self.user.used, "expiry": self.user.expiry_date, "limit": self.user.device_limit,
            "nodes": [(x.user_uuid, x.node_id) for x in self.db.query(UserNode).order_by(UserNode.node_id)],
            "usage": [(x.user_uuid, x.node_id, x.last_usage) for x in self.db.query(UserNodeUsage)],
            "router": [(x.user_uuid, x.node_id, x.router_username, x.password_hash) for x in self.db.query(RouterOpenVpnCredential)],
            "any": [(x.user_uuid, x.password_hash, x.enabled) for x in self.db.query(AnyConnectCredential)],
        }
        with self.patch_client():
            await preflight_job(self.job, self.db)
            await stage_new_identities(self.job, self.db)
            await disable_old_identities(self.job, self.db)
        impl.commit_central_rename(self.job.id, self.db)
        self.db.expire_all(); after = self.db.query(User).filter_by(uuid="u-1").one()
        self.assertEqual(after.name, "new")
        self.assertEqual((after.uuid,after.owner,after.total,after.used,after.expiry_date,after.device_limit), (before["uuid"],before["owner"],before["total"],before["used"],before["expiry"],before["limit"]))
        self.assertEqual([(x.user_uuid,x.node_id) for x in self.db.query(UserNode).order_by(UserNode.node_id)], before["nodes"])
        self.assertEqual([(x.user_uuid,x.node_id,x.last_usage) for x in self.db.query(UserNodeUsage)], before["usage"])
        self.assertEqual([(x.user_uuid,x.node_id,x.router_username,x.password_hash) for x in self.db.query(RouterOpenVpnCredential)], before["router"])
        self.assertEqual([(x.user_uuid,x.password_hash,x.enabled) for x in self.db.query(AnyConnectCredential)], before["any"])
        self.assertEqual(self.db.query(ActiveSession).filter_by(user_uuid="u-1").count(), 0)
        self.assertIsNone(self.db.query(User).filter_by(name="old").first())
        self.assertEqual(self.db.query(User).filter_by(name="new").one().uuid, "u-1")

    async def test_cleanup_failure_keeps_new_name_then_retry_completes_without_reenable(self):
        import backend.user_rename.engine as impl
        self.assertTrue(hasattr(impl, "retry_cleanup"), "retry_cleanup missing")
        self.add_uuid_bound_state()
        with self.patch_client():
            await preflight_job(self.job, self.db); await stage_new_identities(self.job, self.db); await disable_old_identities(self.job, self.db)
        impl.commit_central_rename(self.job.id, self.db)
        self.fake[2].delete_ok = False
        with self.patch_client():
            state = await impl.run_rename_job(self.job.id, self.db)
        self.assertEqual(state, "cleanup_pending")
        self.assertEqual(self.db.query(User).filter_by(uuid="u-1").one().name, "new")
        self.assertNotIn(("old-B", True), self.fake[2].status_calls)
        self.fake[2].delete_ok = True
        with self.patch_client():
            state = await impl.retry_cleanup(self.job.id, self.db)
        self.assertEqual(state, "completed")
        self.assertEqual(self.db.query(User).filter_by(uuid="u-1").one().name, "new")

    async def test_rolling_back_resume_only_compensates(self):
        import backend.user_rename.engine as impl
        self.assertTrue(hasattr(impl, "run_rename_job"), "run_rename_job missing")
        with self.patch_client():
            await preflight_job(self.job, self.db); await stage_new_identities(self.job, self.db)
        evidence = json.loads(self.job.evidence_json); evidence["disabled_old_node_ids"]=[1]
        self.job.evidence_json=json.dumps(evidence); self.job.state="rolling_back"; self.db.commit()
        with self.patch_client():
            state = await impl.run_rename_job(self.job.id, self.db)
        self.assertEqual(state, "rolled_back")
        self.assertEqual(self.db.query(User).filter_by(uuid="u-1").one().name, "old")
        self.assertIn(("old-A", True), self.fake[1].status_calls)



if __name__ == "__main__": unittest.main()
