"""PVN-1047: real native snapshots must enforce retention without a web request."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipIf(os.name=='nt','Native backup durability requires POSIX; run these fixtures on Linux')
class NativeBackupMaintenanceTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('native_disk_test',ROOT/'scripts/pvnetwork_lifecycle.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.backups=self.root/'backups';self.backups.mkdir()
        self.state=self.root/'state';self.state.mkdir();self.app=self.root/'app';self.app.mkdir()
        for name,value in [('BACKUPS',self.backups),('STATE',self.state),('APP',self.app)]:
            patch=mock.patch.object(self.m,name,value);patch.start();self.addCleanup(patch.stop)
        patch=mock.patch.object(self.m,'fsync_directory');patch.start();self.addCleanup(patch.stop)
        self.now=time.time()

    def snapshot(self,stamp,age,pinned=False):
        p=self.backups/stamp;p.mkdir()
        checksums={}
        for name,value in {'database.dump':b'fixture-database','env':b'fixture-env','source.tar.gz':b'fixture-source'}.items():
            (p/name).write_bytes(value);checksums[name]=hashlib.sha256(value).hexdigest()
        (p/'metadata.json').write_text(json.dumps({'format':'pvnetwork-native-backup-v2','checksums':checksums}))
        (p/'RESTORE_TEST_OK').touch()
        if pinned:(p/'.PINNED_BY_TRANSACTION').touch()
        os.utime(p,(self.now-age,self.now-age))
        return p

    def sqlite_environment(self,days):
        db=self.app/'panel.db'
        with sqlite3.connect(db) as c:
            c.execute('CREATE TABLE security_settings(id INTEGER PRIMARY KEY,backup_retention_days INTEGER)')
            c.execute('INSERT INTO security_settings VALUES (1,?)',(days,))
            c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,quota INTEGER)')
            c.execute('INSERT INTO users VALUES (1,12345)')
        (self.app/'VERSION').write_text('1.0.61')
        env={'DATABASE_URL':'sqlite:///'+str(db)}
        (self.app/'.env').write_text('DATABASE_URL='+env['DATABASE_URL']+'\n')
        return env

    def test_real_native_backup_prunes_expired_without_web_request(self):
        expired=self.snapshot('20200101-010101',30*86400)
        pinned=self.snapshot('20200102-010101',29*86400,pinned=True)
        recent=self.snapshot('20200103-010101',86400)
        self.snapshot('20200104-010101',2*86400)
        backup=self.m.make_backup(self.sqlite_environment(10))
        self.assertFalse(expired.exists(),'native scheduled backup never applied retention')
        self.assertTrue(pinned.exists());self.assertTrue(recent.exists())
        self.assertTrue((backup/'RESTORE_TEST_OK').is_file())
        with sqlite3.connect(backup/'database.dump') as db:
            self.assertEqual(db.execute('SELECT quota FROM users').fetchone()[0],12345)

    def test_retention_zero_keeps_expired_backup(self):
        expired=self.snapshot('20200101-010101',30*86400)
        self.m.make_backup(self.sqlite_environment(0))
        self.assertTrue(expired.exists())

    def test_corrupt_expired_checkpoint_survives_beyond_latest_three(self):
        old=self.snapshot('20200101-010101',40*86400)
        (old/'database.dump').write_bytes(b'corrupt preserve for inspection')
        os.utime(old,(self.now-40*86400,self.now-40*86400))
        for day in range(2,5):self.snapshot(f'2020010{day}-010101',86400)
        self.m.prune_native_backups(10,now=self.now)
        self.assertTrue(old.exists(),'damaged backup must survive for deliberate review')

    def test_post_backup_maintenance_failure_preserves_verified_snapshot(self):
        env=self.sqlite_environment(10)
        with mock.patch.object(self.m,'prune_native_backups',side_effect=[[],OSError('fixture cleanup failure')]):
            backup=self.m.make_backup(env)
        self.assertTrue((backup/'RESTORE_TEST_OK').is_file())
        self.assertFalse((backup/'FAILED.json').exists())
        record=json.loads((self.state/'native-backup-maintenance.json').read_text())
        self.assertEqual(record['warnings'],['retention:OSError'])

    def test_pruning_removes_only_expired_known_failed_snapshot(self):
        self.assertTrue(hasattr(self.m,'prune_native_backups'),'native retention implementation missing')
        self.snapshot('20200103-010101',86400)
        failed=self.backups/'20200101-010101';failed.mkdir()
        (failed/'FAILED.json').write_text(json.dumps({'state':'FAILED','verified':False}))
        (failed/'env').write_text('private fixture')
        (failed/'database.dump').write_bytes(b'incomplete fixture')
        os.utime(failed,(self.now-40*86400,self.now-40*86400))
        self.m.prune_native_backups(10,now=self.now)
        self.assertFalse(failed.exists(),'interrupted snapshot payloads must not accumulate indefinitely')

    def test_failed_snapshot_with_unrecovered_database_is_preserved(self):
        self.assertTrue(hasattr(self.m,'prune_native_backups'),'native retention implementation missing')
        self.snapshot('20200103-010101',86400)
        failed=self.backups/'20200101-010101';failed.mkdir()
        (failed/'FAILED.json').write_text(json.dumps({'state':'FAILED','verified':False}))
        (failed/'database-rehearsal.json').write_text(json.dumps({'state':'preparing','temporary_database':'pvnetwork_restore_test_'+'a'*20}))
        os.utime(failed,(self.now-40*86400,self.now-40*86400))
        self.m.prune_native_backups(10,now=self.now)
        self.assertTrue(failed.exists(),'recovery proof must survive until the recorded clone is recovered')

    def test_corrupt_current_recovery_journal_blocks_pruning(self):
        self.assertTrue(hasattr(self.m,'prune_native_backups'),'native retention implementation missing')
        self.snapshot('20200103-010101',86400)
        old=self.snapshot('20200101-010101',40*86400)
        (self.state/'data-transaction.json').write_text('{invalid')
        with self.assertRaises(ValueError):self.m.prune_native_backups(10,now=self.now)
        self.assertTrue(old.exists())

    def test_pruning_preserves_referenced_and_latest_verified_backups(self):
        self.assertTrue(hasattr(self.m,'prune_native_backups'),'native retention implementation missing')
        referenced=self.snapshot('20200101-010101',40*86400)
        latest=self.snapshot('20200102-010101',35*86400)
        (self.state/'lifecycle-transaction.json').write_text(json.dumps({'state':'rolled_back','backup':str(referenced)}))
        removed=self.m.prune_native_backups(10,now=self.now)
        self.assertEqual(removed,[]);self.assertTrue(referenced.exists());self.assertTrue(latest.exists())

    def test_pruning_preserves_unknown_payload_and_symlink_target(self):
        self.assertTrue(hasattr(self.m,'prune_native_backups'),'native retention implementation missing')
        self.snapshot('20200103-010101',86400)
        unknown=self.backups/'20200101-010101';unknown.mkdir();(unknown/'precious').write_text('retain')
        outside=self.root/'outside';outside.mkdir();(outside/'precious').write_text('retain')
        (self.backups/'20200102-010101').symlink_to(outside,target_is_directory=True)
        os.utime(unknown,(self.now-40*86400,self.now-40*86400))
        self.m.prune_native_backups(10,now=self.now)
        self.assertEqual((unknown/'precious').read_text(),'retain')
        self.assertEqual((outside/'precious').read_text(),'retain')

    def test_recovery_updates_only_owned_stale_rehearsal_journal(self):
        self.assertTrue(hasattr(self.m,'recover_backup_rehearsals'),'automatic rehearsal recovery missing')
        p=self.backups/'20200101-010101';p.mkdir();journal=p/'database-rehearsal.json'
        journal.write_text(json.dumps({'state':'preparing','temporary_database':'pvnetwork_restore_test_'+'a'*20}))
        os.utime(journal,(self.now-7200,self.now-7200))
        def drop(record,*,force=True):
            self.assertFalse(force,'background cleanup must never terminate database connections')
            record.pop('temporary_database')
        with mock.patch.object(self.m,'cleanup_recorded_database',side_effect=drop):
            self.m.recover_backup_rehearsals(now=self.now)
        data=json.loads(journal.read_text())
        self.assertNotIn('temporary_database',data)
        self.assertEqual(data['state'],'complete')
        self.assertTrue((p/'FAILED.json').is_file())

    def test_recovery_refuses_other_database_identities_and_fresh_journals(self):
        self.assertTrue(hasattr(self.m,'recover_backup_rehearsals'),'automatic rehearsal recovery missing')
        p=self.backups/'20200101-010101';p.mkdir();journal=p/'database-rehearsal.json'
        journal.write_text(json.dumps({'state':'preparing','temporary_database':'pvnetwork_restored_'+'b'*20}))
        os.utime(journal,(self.now-7200,self.now-7200))
        with self.assertRaisesRegex(ValueError,'rehearsal identity'):
            self.m.recover_backup_rehearsals(now=self.now)
        journal.write_text(json.dumps({'state':'preparing','temporary_database':'pvnetwork_restore_test_'+'a'*20}))
        with mock.patch.object(self.m,'cleanup_recorded_database',side_effect=AssertionError('fresh journal must not be touched')):
            self.assertEqual(self.m.recover_backup_rehearsals(now=self.now),[])

if __name__=='__main__':unittest.main()
