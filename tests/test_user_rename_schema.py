import json
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.engine import Base
from backend.db.models import User

try:
    from backend.user_rename.contracts import RenameState, normalize_rename_username, serialize_rename_job
    from backend.user_rename.repository import (
        LifecycleLocked,
        acquire_lifecycle_lock,
        create_rename_job,
        get_active_lock,
        release_lifecycle_lock,
    )
except ModuleNotFoundError:
    class _MissingState:
        value = "missing"
    class _MissingRenameState:
        QUEUED = _MissingState()
    RenameState = _MissingRenameState
    def _missing(*args, **kwargs):
        raise AssertionError("rename implementation missing")
    class LifecycleLocked(Exception):
        pass
    normalize_rename_username = serialize_rename_job = _missing
    acquire_lifecycle_lock = create_rename_job = get_active_lock = release_lifecycle_lock = _missing


class UserRenameSchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.user = User(name="old_user", uuid="u-1", owner="root", total=0, used=0, expiry_date=__import__('datetime').date.today(), is_active=True, device_limit=1)
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_normalize_username_uses_vpn_safe_contract(self):
        self.assertEqual(normalize_rename_username("new_user-2"), "new_user-2")
        for value in ("ab", "bad name", "bad/slash", "x" * 65):
            with self.assertRaises(ValueError):
                normalize_rename_username(value)

    def test_only_one_lifecycle_lock_exists_per_user_uuid(self):
        first = acquire_lifecycle_lock(self.db, "u-1", "rename", "job-1")
        self.assertEqual(first.user_uuid, "u-1")
        with self.assertRaises(LifecycleLocked):
            acquire_lifecycle_lock(self.db, "u-1", "delete", None)
        self.assertEqual(get_active_lock(self.db, "u-1").operation, "rename")
        release_lifecycle_lock(self.db, "u-1", first.owner_token)
        self.assertIsNone(get_active_lock(self.db, "u-1"))

    def test_status_payload_never_contains_node_secrets_or_profiles(self):
        job = create_rename_job(
            self.db,
            user_uuid="u-1",
            old_name="old_user",
            new_name="new_user",
            actor="root",
            actor_type="main_admin",
            snapshot={"node_ids": [1], "api_key": "secret"},
        )
        job.evidence_json = json.dumps({"profile_bytes": "secret", "private_key": "secret", "nodes": [{"node_id": 1, "name": "de"}]})
        self.db.commit()
        payload = serialize_rename_job(job)
        encoded = json.dumps(payload)
        self.assertNotIn("private_key", encoded)
        self.assertNotIn("profile_bytes", encoded)
        self.assertNotIn("api_key", encoded)
        self.assertEqual(payload["user_uuid"], "u-1")
        self.assertEqual(payload["state"], RenameState.QUEUED.value)

    def test_user_uuid_is_linked_and_not_replaced_by_username(self):
        job = create_rename_job(self.db, user_uuid="u-1", old_name="old_user", new_name="new_user", actor="root", actor_type="main_admin")
        self.assertEqual(job.user_uuid, "u-1")
        self.assertEqual(job.old_name, "old_user")
        self.assertEqual(job.new_name, "new_user")


if __name__ == "__main__":
    unittest.main()
