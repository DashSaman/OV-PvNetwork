"""Native database snapshots and release integrity refusal boundaries."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class LifecycleSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('pvnetwork_lifecycle',ROOT/'scripts/pvnetwork_lifecycle.py')
        cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)

    def test_sqlite_online_backup_restores_committed_wal_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/'live.db';dump=root/'database.dump';restored=root/'restored.db'
            with sqlite3.connect(db) as c:
                c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, quota INTEGER)')
                c.execute('INSERT INTO users VALUES (1,12345)');c.commit()
                self.module.sqlite_snapshot(db,dump)
            expected=self.module.sqlite_fingerprint(dump)
            self.module.sqlite_restore(dump,restored,expected)
            with sqlite3.connect(restored) as c:self.assertEqual(c.execute('SELECT quota FROM users').fetchone()[0],12345)
            self.assertEqual(self.module.sqlite_fingerprint(restored),expected)

    def test_nested_agent_version_does_not_make_root_release_ambiguous(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'source.tar.gz';stage=root/'stage'
            files={'VERSION':b'1.0.43','manifest.json':b'{"version":"1.0.43"}',
                   'frontend/package.json':b'{"version":"1.0.43"}','node-agent/VERSION':b'1.0.43'}
            with tarfile.open(archive,'w:gz') as tar:
                for name,value in files.items():
                    info=tarfile.TarInfo('release/'+name);info.size=len(value);tar.addfile(info,io.BytesIO(value))
            self.module.extract_release(archive,stage,'1.0.43')
            self.assertEqual((stage/'node-agent/VERSION').read_text(),'1.0.43')

    def test_old_code_rollback_transport_guard_uses_live_nodes_and_keeps_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'live.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE nodes(address TEXT,port INTEGER,key TEXT)')
                db.execute("INSERT INTO nodes VALUES ('192.0.2.10',9090,'unchanged-demo-key')")
            env={'DATABASE_URL':'sqlite:///'+str(path)}
            self.assertFalse(self.module.requires_native_node_transport(env))
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE node_tls_bindings(identity TEXT)')
                db.execute('INSERT INTO node_tls_bindings VALUES (?)',(hashlib.sha256(b'192.0.2.10:9090').hexdigest(),))
            before=path.read_bytes()
            self.assertTrue(self.module.requires_native_node_transport(env))
            self.assertEqual(path.read_bytes(),before)

    def test_corrupt_sqlite_restore_never_changes_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'target.db';dump=root/'bad.dump'
            with sqlite3.connect(target) as c:c.execute('CREATE TABLE retained(v TEXT)');c.execute("INSERT INTO retained VALUES ('preserved')")
            before=target.read_bytes();dump.write_bytes(b'invalid snapshot')
            with self.assertRaises((ValueError,sqlite3.DatabaseError)):self.module.sqlite_restore(dump,target,{})
            self.assertEqual(target.read_bytes(),before)

    def test_changed_backup_checksum_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'env').write_text('retained');(root/'database.dump').write_bytes(b'old')
            (root/'source.tar.gz').write_bytes(b'source')
            info={'format':'pvnetwork-native-backup-v2','checksums':{'env':hashlib.sha256((root/'env').read_bytes()).hexdigest(),'database.dump':hashlib.sha256(b'old').hexdigest(),'source.tar.gz':hashlib.sha256(b'source').hexdigest()}}
            (root/'metadata.json').write_text(json.dumps(info));(root/'database.dump').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'backup checksum mismatch'):self.module.verify_backup_files(root)

    def test_runtime_checksum_failure_preserves_existing_encryption_key(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=root/'state';state.mkdir();key=state/'anyconnect-credential-fernet.key';key.write_bytes(b'retained')
            archive=root/'runtime.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                info=tarfile.TarInfo('state/anyconnect-credential-fernet.key');info.size=7;tar.addfile(info,io.BytesIO(b'changed'))
            with mock.patch.object(self.module,'STATE',state),self.assertRaisesRegex(ValueError,'runtime file checksum mismatch'):
                self.module.restore_runtime_files(archive,{'state/anyconnect-credential-fernet.key':hashlib.sha256(b'retained').hexdigest()})
            self.assertEqual(key.read_bytes(),b'retained')

    def test_runtime_restore_preserves_exact_key_and_known_host_bytes(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=root/'state';state.mkdir();app=root/'app';(app/'data').mkdir(parents=True)
            archive=root/'runtime.tar.gz';values={'state/anyconnect-credential-fernet.key':b'private-key','data/ssh_known_hosts':b'known-host-key'}
            with tarfile.open(archive,'w:gz') as tar:
                for name,value in values.items():
                    info=tarfile.TarInfo(name);info.size=len(value);tar.addfile(info,io.BytesIO(value))
            with mock.patch.object(self.module,'APP',app),mock.patch.object(self.module,'STATE',state):
                self.module.restore_runtime_files(archive,{k:hashlib.sha256(v).hexdigest() for k,v in values.items()})
            self.assertEqual((state/'anyconnect-credential-fernet.key').read_bytes(),values['state/anyconnect-credential-fernet.key'])
            self.assertEqual((app/'data/ssh_known_hosts').read_bytes(),values['data/ssh_known_hosts'])
            self.assertEqual((state/'anyconnect-credential-fernet.key').stat().st_mode&0o777,0o600)

    def test_downgrade_is_refused_before_mutation(self):
        with self.assertRaises(ValueError):self.module.validate_upgrade_version('1.0.42','1.0.41')
        with self.assertRaises(ValueError):self.module.validate_upgrade_version('1.0.42','1.0.42')
        self.module.validate_upgrade_version('1.0.41','1.0.42')

    def test_unsafe_release_archive_leaves_stage_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'source.tar.gz';target=root/'stage'
            with tarfile.open(archive,'w:gz') as tar:
                info=tarfile.TarInfo('../outside');data=b'bad';info.size=len(data);tar.addfile(info,io.BytesIO(data))
            with self.assertRaises(ValueError):self.module.extract_release(archive,target,'1.0.42')
            self.assertFalse(target.exists());self.assertFalse((root/'outside').exists())

    def test_atomic_pointer_failure_preserves_previous_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old';old.mkdir();pointer=root/'panel';pointer.symlink_to(old,target_is_directory=True)
            missing=root/'missing'
            with self.assertRaises(ValueError):self.module.atomic_pointer(pointer,missing)
            self.assertEqual(pointer.resolve(),old)

    def test_backup_restores_row_identity_not_just_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a=root/'a.db';b=root/'b.db'
            for p,value in [(a,'preserved'),(b,'changed')]:
                with sqlite3.connect(p) as c:c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, uuid TEXT)');c.execute('INSERT INTO users VALUES (1,?)',(value,))
            self.assertNotEqual(self.module.sqlite_fingerprint(a),self.module.sqlite_fingerprint(b))
