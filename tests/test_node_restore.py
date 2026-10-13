import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(hasattr(os,'geteuid') and os.geteuid()==0,'dedicated isolated root restore fixture gate')
class NodeRestoreTests(unittest.TestCase):
    def modules(self):
        modules={}
        for name in ['pvnetwork_node_install','pvnetwork_node_backup','pvnetwork_node_lifecycle','pvnetwork_node_restore']:
            spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
            value=importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules,modules):spec.loader.exec_module(value)
            modules[name]=value
        return modules['pvnetwork_node_restore']

    def fixture(self,root,restore):
        node=restore.node
        node.STATE=root/'state';node.STATE.mkdir()
        node.RUNTIME=root/'runtime';node.RUNTIME.mkdir()
        node.APP=root/'app';node.APP.mkdir();(node.APP/'VERSION').write_text('1.0.43')
        hooks=root/'hooks';hooks.mkdir();restore.HOOKS=hooks
        config={'host':'node.example.com','mode':'fresh'}
        immutable=node.STATE/'node.env';immutable.write_text('ci-immutable-env');immutable.chmod(0o600)
        hook=hooks/'hooks.env';hook.write_text('ci-working-hook-env');hook.chmod(0o644)
        database=node.RUNTIME/'usage.db'
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,name TEXT NOT NULL,rx INTEGER NOT NULL,tx INTEGER NOT NULL)')
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('a'*64,'ci-demo',10,20))
        files={'state/node.env':immutable,'hooks/hooks.env':hook}
        databases={'runtime/usage.db':database}
        archive=root/'archive.tar.gz'
        restore.backup.create_archive(archive,files,databases,{'host':config['host'],'version':'1.0.43'})
        with sqlite3.connect(database) as db:db.execute('UPDATE sessions SET rx=50,tx=70')
        return archive,files,databases,config

    def test_live_repair_changes_only_owned_hook_and_preserves_newer_counters(self):
        restore=self.modules()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive,files,databases,config=self.fixture(root,restore)
            files['hooks/hooks.env'].write_text('ci-damaged-hook-env')
            with patch.object(restore.backup,'native_files',return_value=(files,databases)),patch.object(restore.lifecycle,'configuration',return_value=config),patch.object(restore.lifecycle,'protected',return_value={'ci':True}),patch.object(restore.lifecycle,'verify_protected'),patch.object(restore.lifecycle,'readiness'),patch.object(restore.node,'run') as run:
                result=restore.restore(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(files['hooks/hooks.env'].read_text(),'ci-working-hook-env')
            with sqlite3.connect(databases['runtime/usage.db']) as db:self.assertEqual(db.execute('SELECT rx,tx FROM sessions').fetchone(),(50,70))
            self.assertFalse(result['vpn_restarted'])
            self.assertFalse(any('openvpn-server@server' in call.args[0] for call in run.call_args_list))

    def test_changed_identity_or_secret_is_refused_before_service_stop(self):
        restore=self.modules()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive,files,databases,config=self.fixture(root,restore)
            files['state/node.env'].write_text('ci-operator-changed-secret')
            with patch.object(restore.backup,'native_files',return_value=(files,databases)),patch.object(restore.lifecycle,'configuration',return_value=config),patch.object(restore.lifecycle,'protected',return_value={'ci':True}),patch.object(restore.node,'run') as run:
                with self.assertRaisesRegex(ValueError,'offline recovery'):
                    restore.restore(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
                run.assert_not_called()
            self.assertEqual(files['state/node.env'].read_text(),'ci-operator-changed-secret')

    def test_failed_health_restores_old_hook_and_retains_post_switch_counters(self):
        restore=self.modules()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive,files,databases,config=self.fixture(root,restore)
            files['hooks/hooks.env'].write_text('ci-before-repair')
            calls=[]
            def readiness(*args):
                if not calls:
                    calls.append(True)
                    with sqlite3.connect(databases['runtime/usage.db']) as db:db.execute('UPDATE sessions SET rx=60,tx=80')
                    raise ValueError('ci-injected-health-failure')
            with patch.object(restore.backup,'native_files',return_value=(files,databases)),patch.object(restore.lifecycle,'configuration',return_value=config),patch.object(restore.lifecycle,'protected',return_value={'ci':True}),patch.object(restore.lifecycle,'verify_protected'),patch.object(restore.lifecycle,'readiness',side_effect=readiness),patch.object(restore.node,'run'):
                with self.assertRaisesRegex(ValueError,'health-failure'):
                    restore.restore(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(files['hooks/hooks.env'].read_text(),'ci-before-repair')
            with sqlite3.connect(databases['runtime/usage.db']) as db:self.assertEqual(db.execute('SELECT rx,tx FROM sessions').fetchone(),(60,80))

    def test_operator_change_after_interruption_is_preserved_before_any_service_stop(self):
        restore=self.modules()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive,files,databases,config=self.fixture(root,restore)
            files['hooks/hooks.env'].write_text('ci-before-repair')
            with patch.object(restore.backup,'native_files',return_value=(files,databases)),patch.object(restore.lifecycle,'configuration',return_value=config),patch.object(restore.lifecycle,'protected',return_value={'ci':True}),patch.object(restore.lifecycle,'verify_protected'),patch.object(restore.node,'run'),patch.object(restore,'recover'),patch.dict(os.environ,{'PVNETWORK_NODE_RESTORE_TEST_FAIL_AT':'switched'}):
                with self.assertRaisesRegex(ValueError,'injected'):
                    restore.restore(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
            files['hooks/hooks.env'].write_text('ci-operator-change')
            with patch.object(restore.lifecycle,'verify_protected'),patch.object(restore.lifecycle,'readiness'),patch.object(restore.node,'run') as run:
                with self.assertRaisesRegex(ValueError,'changed restore target'):
                    restore.recover()
                run.assert_not_called()
            self.assertEqual(files['hooks/hooks.env'].read_text(),'ci-operator-change')

    def test_missing_owned_hook_directory_is_restored_with_public_traversal(self):
        restore=self.modules()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive,files,databases,config=self.fixture(root,restore)
            files['hooks/hooks.env'].unlink();restore.HOOKS.rmdir()
            with patch.object(restore.backup,'native_files',return_value=(files,databases)),patch.object(restore.lifecycle,'configuration',return_value=config),patch.object(restore.lifecycle,'protected',return_value={'ci':True}),patch.object(restore.lifecycle,'verify_protected'),patch.object(restore.lifecycle,'readiness'),patch.object(restore.node,'run'):
                restore.restore(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(restore.HOOKS.stat().st_mode&0o777,0o755)
            self.assertEqual(files['hooks/hooks.env'].read_text(),'ci-working-hook-env')

    def test_changed_rollback_database_is_preserved_before_service_stop(self):
        restore=self.modules()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive,files,databases,config=self.fixture(root,restore)
            files['hooks/hooks.env'].write_text('ci-before-repair')
            with patch.object(restore.backup,'native_files',return_value=(files,databases)),patch.object(restore.lifecycle,'configuration',return_value=config),patch.object(restore.lifecycle,'protected',return_value={'ci':True}),patch.object(restore.lifecycle,'verify_protected'),patch.object(restore.node,'run'),patch.object(restore,'recover'),patch.dict(os.environ,{'PVNETWORK_NODE_RESTORE_TEST_FAIL_AT':'switched'}):
                with self.assertRaisesRegex(ValueError,'injected'):
                    restore.restore(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
            import json
            record=json.loads(restore.journal_path().read_text());previous=Path(record['stage'])/'previous-usage.db'
            with sqlite3.connect(previous) as db:db.execute('UPDATE sessions SET rx=rx+1')
            with patch.object(restore.node,'run') as run:
                with self.assertRaisesRegex(ValueError,'snapshot changed'):
                    restore.recover()
                run.assert_not_called()


if __name__=='__main__':unittest.main()
