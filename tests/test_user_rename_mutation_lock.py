import os
import time
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ADMIN_USERNAME", "testadmin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-at-least-32-characters-long")

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.engine import Base
from backend.db.models import Node, User, UserNode
from backend.schema._input import RenewUser, UpdateUser, UserNodeAssignmentUpdate
from backend.user_rename.repository import acquire_lifecycle_lock, create_rename_job
from backend.routers import users as users_router


class UserMutationLockTests(unittest.IsolatedAsyncioTestCase):
    def make_db(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine, expire_on_commit=False)()
        user = User(uuid="u-1", name="old", owner="root", total=0, used=0, expiry_date=date.today()+timedelta(days=30), is_active=True, device_limit=1)
        node = Node(id=1, name="A", address="10.0.0.1", tunnel_address=None, protocol="tcp", ovpn_port=1194, port=8001, key="k"*16, status=True, drain=False, maintenance=False, weight=100, health_score=100)
        db.add_all([user,node,UserNode(user_uuid="u-1",node_id=1)]); db.commit()
        job = create_rename_job(db,user_uuid="u-1",old_name="old",new_name="new",actor="root",actor_type="main_admin"); db.commit()
        acquire_lifecycle_lock(db,"u-1","rename",job.id); db.commit()
        return engine, db

    async def test_active_rename_lock_blocks_every_conflicting_route_with_409(self):
        actor={"type":"main_admin","username":"root"}
        operations=[
            ("reset", lambda db: users_router.reset_user_usage("u-1",db=db,actor=actor)),
            ("edit", lambda db: users_router.update_user("u-1",UpdateUser(name="old",total=0,expiry_date=date.today()+timedelta(days=30),status=True,device_limit=1),db=db,user=actor)),
            ("renew", lambda db: users_router.renew_user("u-1",RenewUser(duration_days=30,traffic_action="preserve",add_traffic=0),db=db,actor=actor)),
            ("nodes", lambda db: users_router.update_user_nodes("u-1",UserNodeAssignmentUpdate(node_ids=[1]),db=db,actor=actor)),
            ("status", lambda db: users_router.change_user_status("u-1",UpdateUser(name="old",total=0,expiry_date=None,status=False,device_limit=1),db=db,user=actor)),
            ("delete", lambda db: users_router.delete_user("u-1",db=db,user=actor)),
        ]
        for label, call in operations:
            engine,db=self.make_db()
            try:
                with patch("backend.routers.users.reset_shared_user_usage",new=AsyncMock()), patch("backend.routers.users.change_user_status_on_assigned_nodes",new=AsyncMock(return_value=True)), patch("backend.routers.users.replace_user_node_assignments",new=AsyncMock(return_value={"pending_node_ids":[]})), patch("backend.routers.users.delete_user_on_all_nodes",new=AsyncMock(return_value={"failed":[]})), patch("backend.routers.users.revoke_router_credentials_snapshot",new=AsyncMock(return_value={})), patch("backend.routers.users.snapshot_router_credentials_for_user",return_value=[]), patch("backend.routers.users.enforce_user_limits",return_value=None):
                    with self.assertRaises(HTTPException,msg=label) as caught:
                        await call(db)
                self.assertEqual(caught.exception.status_code,409,label)
                detail=caught.exception.detail
                self.assertEqual(detail.get("operation"),"rename")
                self.assertTrue(detail.get("job_id"))
            finally:
                db.close(); engine.dispose()

    def test_transient_lock_contract_exists_and_does_not_steal_rename_lock(self):
        import backend.user_rename.repository as repo
        self.assertTrue(hasattr(repo,"transient_user_mutation_lock"),"transient lock context missing")
        engine,db=self.make_db()
        try:
            with self.assertRaises(repo.LifecycleLocked):
                with repo.transient_user_mutation_lock(db,"u-1","delete"):
                    pass
        finally:
            db.close(); engine.dispose()


if __name__=="__main__": unittest.main()
