"""Live diagnostic writes must not block verified state backups."""
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux', 'Native durable snapshots require Linux file semantics')
class LifecycleLogSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / 'app'
        self.data = self.app / 'data'
        self.data.mkdir(parents=True)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.key = self.state / 'anyconnect-credential-fernet.key'
        self.key.write_bytes(b'fixture-key-not-production')
        self.log = self.data / 'app.log'
        self.log.write_text('old diagnostic\n')
        (self.data / 'fleet_known_hosts').write_text('fixture-host-key')
        (self.data / 'important.log').write_text('unclassified state must be retained')
        (self.app / '.env').write_text('fixture=true\n')
        (self.app / 'VERSION').write_text('1.0.55\n')
        self.database = self.data / 'fixture.db'
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE retained(id INTEGER PRIMARY KEY, value TEXT)')
            db.execute("INSERT INTO retained VALUES (1,'unchanged')")
        self.environment = {'DATABASE_URL': 'sqlite:///' + str(self.database)}
        spec = importlib.util.spec_from_file_location('pvnetwork_log_snapshot', ROOT / 'scripts/pvnetwork_lifecycle.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        for name, value in {'APP': self.app, 'STATE': self.state, 'BACKUPS': self.root / 'backups'}.items():
            patch = mock.patch.object(self.module, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def backup_during(self, change):
        real_snapshot = self.module.sqlite_snapshot
        def snapshot(source, destination):
            fingerprint = real_snapshot(source, destination)
            change()
            return fingerprint
        with mock.patch.object(self.module, 'sqlite_snapshot', side_effect=snapshot):
            return self.module.make_backup(self.environment)

    def test_active_app_log_does_not_block_real_snapshot_and_restore(self):
        directory = self.backup_during(lambda: self.log.write_text('new diagnostic during database snapshot\n'))
        info = self.module.verify_backup_files(directory)
        self.assertTrue((directory / 'RESTORE_TEST_OK').exists())
        self.assertNotIn('data/app.log', info['runtime_fingerprint'])
        self.assertIn('data/important.log', info['runtime_fingerprint'])
        self.assertIn('data/fleet_known_hosts', info['runtime_fingerprint'])
        self.assertIn('state/anyconnect-credential-fernet.key', info['runtime_fingerprint'])
        with tarfile.open(directory / 'source.tar.gz') as source:
            self.assertNotIn(Path('data/app.log'), {Path(member.name) for member in source})
        restored = self.root / 'restored.db'
        self.module.sqlite_restore(directory / 'database.dump', restored, info['fingerprint'])
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute('SELECT * FROM retained').fetchall(), [(1, 'unchanged')])
        self.assertEqual(self.log.read_text(), 'new diagnostic during database snapshot\n')

    def test_key_change_still_refuses_verification(self):
        with self.assertRaisesRegex(ValueError, 'runtime keys/files changed'):
            self.backup_during(lambda: self.key.write_bytes(b'changed-fixture-key'))
        self.assertFalse(list((self.root / 'backups').glob('*/RESTORE_TEST_OK')))

    def test_unclassified_log_change_still_refuses_verification(self):
        with self.assertRaisesRegex(ValueError, 'runtime keys/files changed'):
            self.backup_during(lambda: (self.data / 'important.log').write_text('changed'))


if __name__ == '__main__':
    unittest.main()
