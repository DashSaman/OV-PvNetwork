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
