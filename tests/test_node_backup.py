import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NodeBackupTests(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('node_backup',ROOT/'scripts/pvnetwork_node_backup.py')
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

    def test_actual_file_and_committed_sqlite_restore_rehearsal(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=root/'private.key';key.write_bytes(b'ci-private-key-fixture')
            database=root/'usage.db'
            with sqlite3.connect(database) as db:
                db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,rx INTEGER,tx INTEGER)')
                db.execute("INSERT INTO sessions VALUES ('ci-demo',12345,54321)");db.commit()
                archive=root/'backup/node.tar.gz'
                result=module.create_archive(archive,{'state/tls.key':key},{'runtime/usage.db':database},{'version':'1.0.43'})
            restored=root/'restored';manifest=module.restore_rehearsal(archive,restored)
            self.assertEqual((restored/'state/tls.key').read_bytes(),key.read_bytes())
            with sqlite3.connect(restored/'runtime/usage.db') as db:
                self.assertEqual(db.execute('SELECT rx,tx FROM sessions').fetchone(),(12345,54321))
            self.assertTrue(result['restore_verified']);self.assertEqual(archive.stat().st_mode&0o777,0o600)
            self.assertEqual(manifest['identity'],{'version':'1.0.43'})

    def test_archive_traversal_is_rejected_before_any_target_write(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'bad.tar.gz';target=root/'target'
            with tarfile.open(archive,'w:gz') as tar:
                data=b'bad';member=tarfile.TarInfo('../escape');member.size=len(data);tar.addfile(member,io.BytesIO(data))
            with self.assertRaises(ValueError):module.restore_rehearsal(archive,target)
            self.assertFalse(target.exists());self.assertFalse((root/'escape').exists())

    def test_linked_source_is_refused(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);secret=root/'secret';secret.write_text('ci-private');link=root/'link';link.symlink_to(secret)
            with self.assertRaisesRegex(ValueError,'linked'):
                module.create_archive(root/'backup.tar.gz',{'state/tls.key':link},{},{})
            self.assertFalse((root/'backup.tar.gz').exists())

    def test_backup_records_original_modes_and_ownership_in_private_archive(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=root/'key';key.write_bytes(b'ci-private-key');key.chmod(0o640)
            module.create_archive(root/'backup.tar.gz',{'state/tls.key':key},{},{})
            manifest,_=module.inspect_archive(root/'backup.tar.gz');entry=manifest['files']['state/tls.key']
            self.assertEqual(entry['mode'],0o640)
            self.assertEqual(entry['uid'],key.stat().st_uid);self.assertEqual(entry['gid'],key.stat().st_gid)
            restored=root/'isolated';module.restore_rehearsal(root/'backup.tar.gz',restored)
            self.assertEqual((restored/'state/tls.key').stat().st_mode&0o777,0o600,'rehearsal must stay private')

    def test_accounting_restore_merges_current_session_maxima_and_new_sessions(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old.db';current=root/'current.db'
            for path in [old,current]:
                with sqlite3.connect(path) as db:db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,name TEXT NOT NULL,rx INTEGER NOT NULL,tx INTEGER NOT NULL)')
            with sqlite3.connect(old) as db:db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('a'*64,'ci-demo',100,300))
            with sqlite3.connect(current) as db:
                db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('a'*64,'ci-demo',150,250))
                db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('b'*64,'ci-demo',900,1000))
            module.merge_accounting(old,current)
            with sqlite3.connect(old) as db:self.assertEqual(db.execute('SELECT id,rx,tx FROM sessions ORDER BY id').fetchall(),[('a'*64,150,300),('b'*64,900,1000)])
            with sqlite3.connect(current) as db:self.assertEqual(db.execute('SELECT rx,tx FROM sessions WHERE id=?',('a'*64,)).fetchone(),(150,250))

    def test_conflicting_accounting_identity_is_rejected_without_partial_merge(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old.db';current=root/'current.db'
            for path,name in [(old,'ci-first'),(current,'ci-other')]:
                with sqlite3.connect(path) as db:
                    db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,name TEXT NOT NULL,rx INTEGER NOT NULL,tx INTEGER NOT NULL)')
                    db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('a'*64,name,100,200))
            with self.assertRaisesRegex(ValueError,'identity'):
                module.merge_accounting(old,current)
            with sqlite3.connect(old) as db:self.assertEqual(db.execute('SELECT name,rx,tx FROM sessions').fetchone(),('ci-first',100,200))

    def test_special_permission_archive_is_refused_before_restore_writes(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=root/'key';key.write_bytes(b'ci-private-key')
            original=root/'original.tar.gz';module.create_archive(original,{'state/tls.key':key},{},{})
            manifest,content=module.inspect_archive(original);manifest['files']['state/tls.key']['mode']=0o4755
            bad=root/'bad.tar.gz'
            with tarfile.open(bad,'w:gz') as tar:
                for name,value in [*content.items(),('NODE-BACKUP.json',json.dumps(manifest).encode())]:
                    member=tarfile.TarInfo(name);member.size=len(value);tar.addfile(member,io.BytesIO(value))
            with self.assertRaisesRegex(ValueError,'permissions'):
                module.restore_rehearsal(bad,root/'target')
            self.assertFalse((root/'target').exists())

    def test_accounting_trigger_is_refused_before_merge(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old.db';current=root/'current.db'
            for path in [old,current]:
                with sqlite3.connect(path) as db:db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,name TEXT NOT NULL,rx INTEGER NOT NULL,tx INTEGER NOT NULL)')
            with sqlite3.connect(old) as db:
                db.execute('CREATE TRIGGER unexpected AFTER INSERT ON sessions BEGIN UPDATE sessions SET rx=0; END')
            with sqlite3.connect(current) as db:db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('a'*64,'ci-demo',100,200))
            with self.assertRaisesRegex(ValueError,'schema'):
                module.merge_accounting(old,current)
            with sqlite3.connect(old) as db:self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)

    def test_legacy_conf_leaf_names_are_captured_without_unrelated_server_files(self):
        from types import SimpleNamespace
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=root/'state';vpn=root/'vpn';runtime=root/'runtime'
            state.mkdir();vpn.mkdir();runtime.mkdir()
            (state/'node.env').write_text('ci-private-env')
            (vpn/'server.conf').write_text('ca ca.crt\ncert server.crt\nkey server.key\ntls-crypt tc.key\ncrl-verify crl.pem\n')
            for name in ['ca.crt','server.crt','server.key','tc.key','crl.pem','unrelated.conf']:(vpn/name).write_text('ci-fixture-'+name)
            files,_=module.native_files(SimpleNamespace(STATE=state,SERVER=vpn/'server.conf',RUNTIME=runtime))
            for name in ['ca.crt','server.crt','server.key','tc.key','crl.pem']:self.assertIn('vpn/'+name,files)
            self.assertNotIn('vpn/unrelated.conf',files)
