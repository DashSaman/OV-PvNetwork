import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import sqlite3
from contextlib import closing
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(hasattr(os,'geteuid') and os.geteuid()==0,'offline node recovery ownership fixtures run in the isolated root gate')
class NodeOfflineRestoreTests(unittest.TestCase):
    def module(self):
        modules={}
        for name in ['pvnetwork_node_install','pvnetwork_node_backup','pvnetwork_node_lifecycle','pvnetwork_node_restore']:
            spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'));module=importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules,modules):spec.loader.exec_module(module)
            modules[name]=module
        return modules['pvnetwork_node_restore']

    def fixture(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name);restore=self.module();node=restore.node
        node.STATE=root/'state';node.STATE.mkdir(mode=0o700);node.RUNTIME=root/'runtime';node.RUNTIME.mkdir(mode=0o700)
        node.SERVER=root/'vpn/server.conf';node.SERVER.parent.mkdir();node.APP=root/'app';node.APP.mkdir();(node.APP/'VERSION').write_text('1.0.43')
        restore.HOOKS=root/'hooks';restore.HOOKS.mkdir();restore.CCD=root/'ccd';restore.CCD.mkdir();restore.PROFILES=root/'profiles';restore.PROFILES.mkdir()
        node.JOURNAL=node.STATE/'transaction.json'
        config={'host':'node.example.com','protocol':'udp','ovpn_port':1194,'mode':'fresh'}
        journal={'id':'a'*24,'phase':'finalized','configuration':config,'version':'1.0.43'}
        files={'state/transaction.json':node.JOURNAL,'state/node.env':node.STATE/'node.env','vpn/server.conf':node.SERVER,'vpn/easy-rsa/pki/ca.crt':node.SERVER.parent/'easy-rsa/pki/ca.crt','vpn/easy-rsa/pki/private/ca.key':node.SERVER.parent/'easy-rsa/pki/private/ca.key','vpn/easy-rsa/pki/index.txt':node.SERVER.parent/'easy-rsa/pki/index.txt'}
        values={name:b'ci-private-owned-material' for name in files};values['state/transaction.json']=json.dumps(journal).encode();values['vpn/server.conf']=b'port 1194\nproto udp\n';values['vpn/easy-rsa/pki/index.txt']=b'V\t351231000000Z\t\t01\tunknown\t/CN=ci-demo\n'
        for name,path in files.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(values[name]);path.chmod(0o600)
        archive=root/'backup.tar.gz';restore.backup.create_archive(archive,files,{}, {'host':config['host'],'version':'1.0.43'})
        return restore,archive,files,config

    def test_offline_plan_maps_only_declared_roots_and_missing_PKI(self):
        restore,archive,files,config=self.fixture();files['vpn/easy-rsa/pki/private/ca.key'].unlink()
        manifest,plan=restore.offline_plan(archive,config)
        self.assertEqual(plan['vpn/easy-rsa/pki/private/ca.key']['target'],str(files['vpn/easy-rsa/pki/private/ca.key']))
        self.assertFalse(files['vpn/easy-rsa/pki/private/ca.key'].exists())
        self.assertEqual(manifest['identity']['host'],config['host'])

    def test_new_customer_serial_refuses_restore_before_service_changes(self):
        restore,archive,files,config=self.fixture()
        files['vpn/easy-rsa/pki/index.txt'].write_bytes(files['vpn/easy-rsa/pki/index.txt'].read_bytes()+b'V\t351231000000Z\t\t02\tunknown\t/CN=new-customer\n')
        with patch.object(restore.node,'run') as run:
            with self.assertRaises(ValueError):restore.offline_plan(archive,config)
            self.assertEqual(run.call_count,0)

    def test_external_or_foreign_backup_scope_refuses_before_writes(self):
        restore,archive,files,config=self.fixture()
        extra=Path(self.temp.name)/'foreign';extra.write_bytes(b'foreign-service')
        bad=Path(self.temp.name)/'bad.tar.gz';restore.backup.create_archive(bad,{**files,'state/foreign-service':extra},{},{'host':config['host'],'version':'1.0.43'})
        with self.assertRaises(ValueError):restore.offline_plan(bad,config)
        self.assertEqual(extra.read_bytes(),b'foreign-service')

    def test_actual_offline_restore_replaces_missing_owned_key_with_original_metadata(self):
        restore,archive,files,config=self.fixture();key=files['vpn/easy-rsa/pki/private/ca.key'];original=key.read_bytes();key.unlink()
        with patch.object(restore,'offline_services',return_value={'pvnetwork-node':False,'pvnetwork-domain-collector':False,'openvpn-server@server':False}),patch.object(restore,'verify_offline_runtime'),patch.object(restore.node,'run') as run:
            result=restore.restore_offline(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(result['state'],'complete');self.assertEqual(key.read_bytes(),original);self.assertEqual(key.stat().st_mode&0o777,0o600)
        self.assertFalse(any(call.args[0][1] in {'start','restart'} for call in run.call_args_list if call.args[0][0]=='systemctl'))

    def test_offline_failure_restores_damaged_preoperation_files(self):
        restore,archive,files,config=self.fixture();key=files['vpn/easy-rsa/pki/private/ca.key'];key.write_bytes(b'pre-operation-damaged-key')
        with patch.object(restore,'offline_services',return_value={'pvnetwork-node':False,'pvnetwork-domain-collector':False,'openvpn-server@server':False}),patch.object(restore,'verify_offline_runtime',side_effect=ValueError('ci-offline-health-failure')),patch.object(restore.node,'run'):
            with self.assertRaises(ValueError):restore.restore_offline(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(key.read_bytes(),b'pre-operation-damaged-key')
        self.assertEqual(json.loads(restore.journal_path().read_text())['state'],'rolled_back')

    def test_WAL_current_counters_survive_offline_restore(self):
        restore,archive,files,config=self.fixture();database=restore.node.RUNTIME/'usage.db'
        with closing(sqlite3.connect(database)) as db,db:
            db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,name TEXT NOT NULL,rx INTEGER NOT NULL,tx INTEGER NOT NULL)')
            db.execute('INSERT INTO sessions VALUES (?,?,?,?)',('a'*64,'ci-demo',10,20))
        restore.backup.create_archive(Path(self.temp.name)/'wal-backup.tar.gz',files,{'runtime/usage.db':database},{'host':config['host'],'version':'1.0.43'})
        archive=Path(self.temp.name)/'wal-backup.tar.gz'
        with closing(sqlite3.connect(database)) as db,db:
            db.execute('PRAGMA journal_mode=WAL');db.execute('UPDATE sessions SET rx=90,tx=110');db.commit()
        with patch.object(restore,'offline_services',return_value={'pvnetwork-node':False,'pvnetwork-domain-collector':False,'openvpn-server@server':False}),patch.object(restore,'verify_offline_runtime'),patch.object(restore.node,'run'):
            result=restore.restore_offline(archive,hashlib.sha256(archive.read_bytes()).hexdigest())
        with sqlite3.connect(database) as db:self.assertEqual(db.execute('SELECT rx,tx FROM sessions').fetchone(),(90,110))
        self.assertTrue(result['current_counters_preserved'])

    def test_adopted_service_restart_refreshes_private_journal_PID(self):
        restore,archive,files,config=self.fixture();config['mode']='adopt'
        journal=json.loads(files['state/transaction.json'].read_text());journal['configuration']=config;journal['adopted']={'pid':'41'}
        files['state/transaction.json'].write_text(json.dumps(journal))
        updated=Path(self.temp.name)/'adopted.tar.gz';restore.backup.create_archive(updated,files,{}, {'host':config['host'],'version':'1.0.43'})
        files['vpn/easy-rsa/pki/private/ca.key'].unlink()
        with patch.object(restore,'offline_services',return_value={'pvnetwork-node':False,'pvnetwork-domain-collector':False,'openvpn-server@server':True}),patch.object(restore,'verify_offline_runtime'),patch.object(restore.node,'adopted_snapshot',return_value={'pid':'42'}),patch.object(restore.node,'run'):
            result=restore.restore_offline(updated,hashlib.sha256(updated.read_bytes()).hexdigest())
        self.assertEqual(result['state'],'complete')
        self.assertEqual(json.loads(restore.node.JOURNAL.read_text())['adopted']['pid'],'42')
        record=json.loads(restore.journal_path().read_text());self.assertTrue(record['journal_variants'])


if __name__=='__main__':unittest.main()
