"""Interrupted fresh PKI never becomes a live partial server directory."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name=='posix' and os.geteuid()==0,'dedicated root-owned Linux fixture required')
class FreshPkiStagingTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        spec=importlib.util.spec_from_file_location('fresh_pki_node',ROOT/'scripts/pvnetwork_node_install.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.m.SERVER=self.root/'openvpn/server/server.conf';self.m.SERVER.parent.parent.mkdir()
        self.m.STATE=self.root/'state';self.m.STATE.mkdir(mode=0o700);self.m.JOURNAL=self.m.STATE/'transaction.json'
        self.m.APP=self.root/'agent';self.m.RELEASES=self.root/'releases'
        self.record={'id':'a'*24,'mode':'fresh','phase':'build','created_files':[],'configuration':{}}

    def tearDown(self):self.folder.cleanup()

    def rollback(self):
        with patch.object(self.m,'run'),patch.object(self.m.subprocess,'run'):
            self.m.rollback(self.record)

    def test_partial_private_CA_is_retained_and_rollback_unblocks_retry(self):
        stage=self.m.prepare_fresh_vpn(self.record)
        (stage/'partial-ca.key').write_bytes(b'private-demo-partial-CA');(stage/'partial-ca.key').chmod(0o600)
        self.assertFalse(self.m.SERVER.parent.exists())
        self.rollback()
        self.assertEqual(self.record['phase'],'rolled_back')
        self.assertEqual((stage/'partial-ca.key').read_bytes(),b'private-demo-partial-CA')
        self.assertFalse(self.m.SERVER.parent.exists())
        next_record={**self.record,'id':'b'*24}
        next_stage=self.m.prepare_fresh_vpn(next_record)
        self.assertNotEqual(stage,next_stage)
        self.assertTrue(stage.exists())

    def test_completed_inventory_is_journaled_before_publish_and_rollback_preserves_empty_parent_mode(self):
        self.m.SERVER.parent.mkdir(mode=0o750)
        stage=self.m.prepare_fresh_vpn(self.record)
        (stage/'server.conf').write_bytes(b'complete-demo-config')
        self.m.publish_fresh_vpn(self.record,stage)
        self.assertFalse(stage.exists());self.assertEqual(self.m.SERVER.read_bytes(),b'complete-demo-config')
        self.assertEqual(self.record['owned_vpn_sha256'],{'server.conf':self.m.hash_file(self.m.SERVER)})
        self.rollback()
        self.assertEqual(self.m.SERVER.parent.stat().st_mode&0o777,0o750)
        self.assertEqual(list(self.m.SERVER.parent.iterdir()),[])
        self.assertEqual((stage/'server.conf').read_bytes(),b'complete-demo-config')
        self.assertEqual(stage.stat().st_mode&0o777,0o700)

    def test_operator_files_created_during_build_are_preserved_before_publication(self):
        stage=self.m.prepare_fresh_vpn(self.record)
        (stage/'server.conf').write_bytes(b'candidate-config')
        self.m.SERVER.parent.mkdir();foreign=self.m.SERVER.parent/'operator.crt';foreign.write_bytes(b'preserved')
        with self.assertRaisesRegex(ValueError,'changed|appeared'):
            self.m.publish_fresh_vpn(self.record,stage)
        self.assertEqual(foreign.read_bytes(),b'preserved')
        self.assertTrue(stage.exists())

    def test_failed_atomic_rename_preserves_private_stage_and_restores_original_empty_directory(self):
        self.m.SERVER.parent.mkdir(mode=0o750)
        stage=self.m.prepare_fresh_vpn(self.record);(stage/'server.conf').write_bytes(b'complete-config')
        original_replace=self.m.os.replace
        def interrupted(source,target):
            if Path(source)==stage:raise OSError('injected rename failure')
            return original_replace(source,target)
        with patch.object(self.m.os,'replace',side_effect=interrupted),self.assertRaisesRegex(OSError,'injected'):
            self.m.publish_fresh_vpn(self.record,stage)
        self.assertFalse(self.m.SERVER.parent.exists())
        self.rollback()
        self.assertEqual(self.record['phase'],'rolled_back')
        self.assertEqual(self.m.SERVER.parent.stat().st_mode&0o777,0o750)
        self.assertEqual((stage/'server.conf').read_bytes(),b'complete-config')

    def test_partial_easyrsa_failure_preserves_CA_and_never_creates_live_configuration(self):
        def copy_fixture(source,target):
            target.mkdir();(target/'easyrsa').write_text('demo-fixture')
        def fail_after_CA(arguments,**kwargs):
            easy=Path(arguments[0]).parent;private=easy/'pki/private';private.mkdir(parents=True,exist_ok=True)
            (private/'ca.key').write_bytes(b'preserved-demo-CA');(private/'ca.key').chmod(0o600)
            raise RuntimeError('injected EasyRSA failure')
        with patch.object(self.m.shutil,'copytree',side_effect=copy_fixture),patch.object(self.m,'run',side_effect=fail_after_CA),self.assertRaisesRegex(RuntimeError,'injected'):
            self.m.fresh_vpn({'protocol':'udp','host':'node.example.com','ovpn_port':1194},self.record)
        self.rollback()
        self.assertEqual(self.record['phase'],'rolled_back')
        self.assertFalse(self.m.SERVER.parent.exists())
        retained=Path(self.record['retained_vpn_staging'])/'easy-rsa/pki/private/ca.key'
        self.assertEqual(retained.read_bytes(),b'preserved-demo-CA')
        self.assertEqual(retained.stat().st_mode&0o777,0o600)

    def test_published_before_final_journal_is_recognized_and_retained_on_recovery(self):
        stage=self.m.prepare_fresh_vpn(self.record);(stage/'server.conf').write_bytes(b'complete-config')
        original_checkpoint=self.m.checkpoint
        def interrupted(record,phase):
            if record.get('vpn_published'):raise RuntimeError('interruption after rename before final journal')
            original_checkpoint(record,phase)
        with patch.object(self.m,'checkpoint',side_effect=interrupted),self.assertRaisesRegex(RuntimeError,'after rename'):
            self.m.publish_fresh_vpn(self.record,stage)
        import json
        self.record=json.loads(self.m.JOURNAL.read_text())
        self.assertNotIn('vpn_published',self.record)
        self.rollback()
        self.assertFalse(self.m.SERVER.parent.exists())
        self.assertEqual((stage/'server.conf').read_bytes(),b'complete-config')

    def test_shared_write_artifact_refused_before_live_directory_change(self):
        stage=self.m.prepare_fresh_vpn(self.record)
        (stage/'unsafe.key').write_bytes(b'preserve-fixture-key');(stage/'unsafe.key').chmod(0o666)
        with self.assertRaisesRegex(ValueError,'unsafe private PKI artifact'):
            self.m.publish_fresh_vpn(self.record,stage)
        self.assertFalse(self.m.SERVER.parent.exists())
        self.rollback()
        self.assertEqual((stage/'unsafe.key').read_bytes(),b'preserve-fixture-key')

    def test_interrupted_empty_directory_restoration_replays_without_deleting_PKI(self):
        self.m.SERVER.parent.mkdir(mode=0o750)
        stage=self.m.prepare_fresh_vpn(self.record);(stage/'server.conf').write_bytes(b'complete-config')
        self.m.publish_fresh_vpn(self.record,stage)
        with patch.object(self.m.os,'chown',side_effect=OSError('injected empty-directory ownership interruption')),self.assertRaisesRegex(OSError,'ownership interruption'):
            self.rollback()
        import json
        self.record=json.loads(self.m.JOURNAL.read_text())
        self.assertTrue(self.record['vpn_empty_restore_pending'])
        self.rollback()
        self.assertEqual(self.record['phase'],'rolled_back')
        self.assertEqual(self.m.SERVER.parent.stat().st_mode&0o777,0o750)
        self.assertEqual((stage/'server.conf').read_bytes(),b'complete-config')
