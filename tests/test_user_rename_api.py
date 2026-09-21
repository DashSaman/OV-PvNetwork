import os
import unittest
from datetime import date
from types import SimpleNamespace

os.environ.setdefault("ADMIN_USERNAME","testadmin")
os.environ.setdefault("ADMIN_PASSWORD_HASH","$2b$12$abcdefghijklmnopqrstuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu")
os.environ.setdefault("JWT_SECRET_KEY","test-only-jwt-secret-key-at-least-32-characters-long")

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.engine import Base
from backend.db.models import User, UserLifecycleLock, UserRenameJob
from backend.routers import users as users_router


class RenameApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine=create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine); self.db=sessionmaker(bind=self.engine,expire_on_commit=False)()
        self.db.add_all([
            User(uuid="u-own",name="alice",owner="seller",total=0,used=0,expiry_date=date(2030,1,1),is_active=True,device_limit=1),
            User(uuid="u-other",name="bob",owner="other",total=0,used=0,expiry_date=date(2030,1,1),is_active=True,device_limit=1),
        ]); self.db.commit()
        self.actor={"type":"main_admin","username":"root"}

    def tearDown(self): self.db.close(); self.engine.dispose()

    async def queue(self, uuid, name):
        self.assertTrue(hasattr(users_router,"queue_user_rename"),"queue endpoint missing")
        return await users_router.queue_user_rename(uuid,SimpleNamespace(new_username=name),db=self.db,actor=self.actor)

    async def test_queue_commits_job_plus_nonexpiring_lock_and_route_is_202(self):
        result=await self.queue("u-own","alice_new")
        self.assertTrue(result.success)
        job=self.db.query(UserRenameJob).one(); lock=self.db.query(UserLifecycleLock).one()
        self.assertEqual(job.user_uuid,"u-own"); self.assertEqual(job.state,"queued")
        self.assertEqual(lock.operation,"rename"); self.assertEqual(lock.job_id,job.id); self.assertIsNone(lock.expires_at)
        self.assertEqual(self.db.query(User).filter_by(uuid="u-own").one().name,"alice")
        route=next(r for r in users_router.router.routes if r.path.endswith("/{uuid}/rename") and "POST" in r.methods)
        self.assertEqual(route.status_code,202)

    async def test_queue_rejects_noop_collision_and_second_rename(self):
        with self.assertRaises(HTTPException) as noop: await self.queue("u-own","alice")
        self.assertEqual(noop.exception.status_code,422)
        with self.assertRaises(HTTPException) as collision: await self.queue("u-own","bob")
        self.assertEqual(collision.exception.status_code,409)
        await self.queue("u-own","alice_new")
        with self.assertRaises(HTTPException) as second: await self.queue("u-own","alice_two")
        self.assertEqual(second.exception.status_code,409)

    async def test_delegated_admin_ownership_and_active_job_filtering(self):
        self.actor={"type":"admin","username":"seller"}
        await self.queue("u-own","alice_new")
        with self.assertRaises(HTTPException) as other: await self.queue("u-other","bob_new")
        self.assertEqual(other.exception.status_code,404)
        self.assertTrue(hasattr(users_router,"get_active_rename_jobs"),"active jobs endpoint missing")
        active=await users_router.get_active_rename_jobs(db=self.db,actor=self.actor)
        jobs=active.data
        self.assertEqual([j["user_uuid"] for j in jobs],["u-own"])
        job_id=jobs[0]["id"]
        status=await users_router.get_user_rename_status("u-own",job_id,db=self.db,actor=self.actor)
        self.assertEqual(status.data["user_uuid"],"u-own")
        with self.assertRaises(HTTPException) as hidden:
            await users_router.get_user_rename_status("u-other",job_id,db=self.db,actor=self.actor)
        self.assertEqual(hidden.exception.status_code,404)


if __name__=="__main__": unittest.main()
