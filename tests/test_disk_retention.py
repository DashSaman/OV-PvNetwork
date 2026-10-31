"""Safe native backup expiry tests; never act on real server paths."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class NativeBackupRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "pvnetwork_lifecycle_disk_test", ROOT / "scripts/pvnetwork_lifecycle.py"
        )
        cls.lifecycle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.lifecycle)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backups = self.root / "backups"
        self.backups.mkdir()
        self.state = self.root / "state"
        self.state.mkdir()
        self.patches = [
            mock.patch.object(self.lifecycle, "BACKUPS", self.backups),
            mock.patch.object(self.lifecycle, "STATE", self.state),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.now = datetime.datetime(2026, 10, 31, tzinfo=datetime.timezone.utc)
        self.old = self.now.timestamp() - (40 * 86400)

    def add_verified(self, name):
        directory = self.backups / name
        directory.mkdir()
        payload = {
            "database.dump": b"database",
            "env": b"environment",
            "source.tar.gz": b"archive",
        }
        for filename, value in payload.items():
            (directory / filename).write_bytes(value)
        metadata = {
            "format": "pvnetwork-native-backup-v2",
            "checksums": {
                filename: hashlib.sha256(value).hexdigest()
                for filename, value in payload.items()
            },
        }
        (directory / "metadata.json").write_text(json.dumps(metadata))
        (directory / "RESTORE_TEST_OK").touch()
        os.utime(directory, (self.old, self.old))
        return directory

    def test_expired_verified_only_keep_latest_three_pinned_and_invalid(self):
        names = [f"202609{day:02d}-032000" for day in range(1, 8)]
        paths = [self.add_verified(name) for name in names]
        # Three newest are never touched.
        (paths[3] / ".PINNED_BY_TRANSACTION").touch()
        (paths[2] / "database.dump").write_bytes(b"invalid")
        # Old generations: 1 unpinned verified deleted, one pinned preserved.
        (paths[1] / "database.dump").write_bytes(b"corrupt")
        unrelated = self.backups / "notes"
        unrelated.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (self.backups / "20260801-032000").symlink_to(outside, target_is_directory=True)
        self.assertEqual(
            self.lifecycle.prune_expired_backups(retention_days=10, now=self.now),
            1,
        )
        self.assertFalse(paths[0].exists())
        for path in paths[1:]:
            self.assertTrue(path.exists(), path.name)
        self.assertTrue(unrelated.exists())
        self.assertTrue(outside.exists())

    def test_zero_disables_pruning(self):
        old = self.add_verified("20260901-032000")
        self.assertEqual(self.lifecycle.prune_expired_backups(retention_days=0, now=self.now), 0)
        self.assertTrue(old.exists())

    def test_very_recent_backups_are_preserved_even_when_beyond_three(self):
        for index in range(5):
            path = self.add_verified(f"202610{20 + index:02d}-032000")
            os.utime(path, (self.now.timestamp(), self.now.timestamp()))
        self.assertEqual(self.lifecycle.prune_expired_backups(retention_days=10, now=self.now), 0)

    def test_current_pointer_is_protected(self):
        names = [f"202609{day:02d}-032000" for day in range(1, 6)]
        paths = [self.add_verified(name) for name in names]
        (self.state / "last-native-backup.json").write_text(
            json.dumps({"backup": str(paths[0])})
        )
        self.assertEqual(self.lifecycle.prune_expired_backups(retention_days=10, now=self.now), 1)
        self.assertTrue(paths[0].exists())
        self.assertFalse(paths[1].exists())

    def test_root_symlink_is_rejected(self):
        another = self.root / "another"
        another.mkdir()
        linked = self.root / "linked"
        linked.symlink_to(another, target_is_directory=True)
        with mock.patch.object(self.lifecycle, "BACKUPS", linked):
            with self.assertRaisesRegex(ValueError, "backup root"):
                self.lifecycle.prune_expired_backups(retention_days=10, now=self.now)

    def test_retained_backup_prunes_before_and_after(self):
        with mock.patch.object(self.lifecycle, "prune_expired_backups", side_effect=[1, 2]) as prune:
            with mock.patch.object(self.lifecycle, "make_backup", return_value=self.backups / "new") as make:
                result = self.lifecycle.make_retained_backup()
        self.assertEqual(result["expired_backups_removed"], 3)
        self.assertTrue(result["verified"])
        self.assertFalse(result["retention_warning"])
        self.assertEqual(prune.call_count, 2)
        make.assert_called_once_with()

    def test_cleanup_failure_never_prevents_verified_backup(self):
        with mock.patch.object(self.lifecycle, "prune_expired_backups", side_effect=OSError("I/O error")):
            with mock.patch.object(self.lifecycle, "make_backup", return_value=self.backups / "new"):
                result = self.lifecycle.make_retained_backup()
        self.assertTrue(result["retention_warning"])
        self.assertTrue(result["verified"])


if __name__ == "__main__":
    unittest.main()

