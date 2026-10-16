import importlib.util
import hashlib
import os
from pathlib import Path
import sys
import io
import tarfile
import shutil
import json
import unittest
from unittest.mock import patch

from tests import test_client_profile_identity as profiles

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(hasattr(os,'geteuid') and os.geteuid()==0,'configuration ownership fixtures run in the isolated root gate')
class NodeConfigurationTransactionTests(unittest.TestCase):
    def setUp(self):
        fixture=profiles.ClientProfileIdentityTests();fixture.setUp()
        self.addCleanup(fixture.temp.cleanup);self.fixture=fixture;self.root=fixture.root
        self.server=self.root/'server.conf';self.server.write_bytes(b'port 1194\nproto udp\n# preserved operator setting\n')
        self.template=self.root/'client-template.txt';self.template.write_bytes(b'client\nremote node.example.com 1194\nproto udp\n')
        spec=importlib.util.spec_from_file_location('pvnetwork_node_install',ROOT/'scripts/pvnetwork_node_install.py')
        self.node=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.node)
        spec=importlib.util.spec_from_file_location('node_configuration',ROOT/'scripts/pvnetwork_node_configure.py')
        self.module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'pvnetwork_node_install':self.node}):spec.loader.exec_module(self.module)
        self.module.SERVER=self.server;self.module.TEMPLATES=[self.template]
        self.module.PROFILES=self.root;self.module.PKI=fixture.pki
        self.record={'id':'a'*24,'phase':'finalized','configuration':{'host':'api.example.com','mode':'fresh','protocol':'udp','ovpn_port':1194}}
        self.module.NETWORK=self.root/'network-helper'
        self.module.NETWORK.write_text(self.node.network_script(self.record));self.module.NETWORK.chmod(0o755)

    def request(self,**changes):
        return {'protocol':'udp','ovpn_port':1194,'tunnel_address':'node.example.com','set_new_setting':True,**changes}

    def test_plan_changes_owned_headers_without_touching_crypto_or_API_identity(self):
        original=self.fixture.profile.read_bytes();foreign=self.root/'foreign.ovpn';foreign.write_bytes(b'unrelated VPN profile')
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        plan=self.module.prepare(self.record,self.request(protocol='tcp',ovpn_port=443,tunnel_address='vpn.example.com'))
        self.assertEqual(plan['configuration']['host'],'api.example.com')
        self.assertEqual(plan['configuration']['tunnel_address'],'vpn.example.com')
        self.assertTrue(plan['vpn_restart'])
        updates=plan['updates'];changed=updates[str(self.fixture.profile)]['content']
        self.assertEqual(changed[changed.index(b'<ca>'):],original[original.index(b'<ca>'):])
        self.assertIn(b'remote vpn.example.com 443\nproto tcp-client\n',changed)
        self.assertNotIn(str(foreign),updates)
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_endpoint_only_and_noop_plan_do_not_request_VPN_restart(self):
        self.assertFalse(self.module.prepare(self.record,self.request())['updates'])
        plan=self.module.prepare(self.record,self.request(tunnel_address='vpn.example.com'))
        self.assertFalse(plan['vpn_restart']);self.assertNotIn(str(self.server),plan['updates'])

    def test_endpoint_preservation_ignores_directive_text_inside_inline_material(self):
        self.template.write_bytes(b'<tls-crypt-v2>\nremote inline.example.com 9999\n</tls-crypt-v2>\n'+self.template.read_bytes())
        plan=self.module.prepare(self.record,self.request(tunnel_address=''))
        self.assertFalse(plan['updates']);self.assertFalse(plan['vpn_restart'])

    def test_semantic_noop_preserves_server_spacing_and_address_family(self):
        self.server.write_bytes(b'port\t1194\nproto\tudp4\n# preserve\n')
        plan=self.module.prepare(self.record,self.request())
        self.assertFalse(plan['updates']);self.assertFalse(plan['vpn_restart'])

    def test_new_port_conflict_refuses_before_any_file_write(self):
        original=self.server.read_bytes()
        with patch.object(self.node,'host_facts',return_value={'listeners':{('tcp',443)}}):
            with self.assertRaises(ValueError):self.module.prepare(self.record,self.request(protocol='tcp',ovpn_port=443))
        self.assertEqual(self.server.read_bytes(),original)

    def test_conflicting_own_profile_or_stale_journal_refuses_before_any_write(self):
        original=self.server.read_bytes();self.fixture.profile.write_bytes(self.fixture.content('bob'))
        with self.assertRaises(ValueError):self.module.prepare(self.record,self.request(ovpn_port=443))
        self.assertEqual(self.server.read_bytes(),original)
        self.fixture.profile.write_bytes(self.fixture.content('alice'))
        self.record['configuration']['ovpn_port']=1195
        with self.assertRaises(ValueError):self.module.prepare(self.record,self.request(ovpn_port=443))
        self.assertEqual(self.server.read_bytes(),original)

    def test_adopted_input_only_rule_does_not_change_global_forwarding(self):
        tag='pvnetwork-node-'+self.record['id']
        record={**self.record,'firewall_rules':[['INPUT','-p','tcp','--dport','443','-m','comment','--comment',tag,'-j','ACCEPT']]}
        script=self.node.network_script(record)
        self.assertNotIn('sysctl',script)
        self.assertIn('iptables -w -C INPUT -p tcp --dport 443',script)

    def test_network_plan_preserves_API_rules_and_refuses_changed_owned_helper(self):
        tag='pvnetwork-node-'+self.record['id']
        self.record['api_rules']=[['iptables',['INPUT','-p','tcp','--dport','9443','-s','192.0.2.11','-m','comment','--comment',tag+'-api','-j','ACCEPT']]]
        self.module.NETWORK.write_text(self.node.network_script(self.record))
        original=self.module.NETWORK.read_bytes()
        config={**self.record['configuration'],'protocol':'tcp','ovpn_port':443}
        next_record,item=self.module.network_plan(self.record,config)
        self.assertEqual(self.module.NETWORK.read_bytes(),original)
        self.assertIn(b'--dport 443',item['content']);self.assertNotIn(b'sysctl',item['content'])
        self.assertEqual(next_record['configuration']['host'],'api.example.com')
        self.assertEqual(next_record['api_rules'],self.record['api_rules'])
        self.module.NETWORK.write_bytes(b'operator changed helper')
        with self.assertRaises(ValueError):self.module.network_plan(self.record,config)
        self.assertEqual(self.module.NETWORK.read_bytes(),b'operator changed helper')

    def test_previous_verified_network_rendering_uses_recorded_digest(self):
        self.module.NETWORK.write_bytes(b'#!/bin/sh\nset -eu\n# earlier verified rendering\n')
        self.record['created_file_sha256']={str(self.module.NETWORK):hashlib.sha256(self.module.NETWORK.read_bytes()).hexdigest()}
        config={**self.record['configuration'],'protocol':'tcp','ovpn_port':443}
        updated,item=self.module.network_plan(self.record,config)
        self.assertEqual(updated['created_file_sha256'][str(self.module.NETWORK)],hashlib.sha256(item['content']).hexdigest())
        self.module.NETWORK.write_bytes(b'operator changed prior helper')
        with self.assertRaises(ValueError):self.module.network_plan(self.record,config)

    def test_versioned_management_helpers_are_verified_and_existing_directory_is_preserved(self):
        from backend.node.deploy import build_native_node_bundle
        payload,_=build_native_node_bundle()
        source=self.root/'source';source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:archive.extractall(source,filter='data')
        release=self.root/'candidate';shutil.copytree(source/'node-agent',release)
        self.node.stage_resources(source,release)
        helpers=release/'resources'
        self.assertEqual((helpers/'pvnetwork_node_configure.py').read_bytes(),(source/'scripts/pvnetwork_node_configure.py').read_bytes())
        self.assertEqual((helpers/'pvnetwork-build-client-profile').read_bytes(),(source/'scripts/pvnetwork-build-client-profile').read_bytes())
        self.assertFalse((helpers/'.env').exists())
        self.assertEqual((helpers/'pvnetwork_node_install.py').stat().st_mode&0o777,0o644)
        marker=helpers/'operator';marker.write_bytes(b'preserve')
        with self.assertRaises(ValueError):self.node.stage_resources(source,release)
        self.assertEqual(marker.read_bytes(),b'preserve')
        (source/'scripts/pvnetwork_node_configure.py').write_bytes(b'altered verified source')
        empty=self.root/'bad-candidate';empty.mkdir()
        with self.assertRaises(ValueError):self.node.stage_resources(source,empty)
        self.assertFalse((empty/'resources').exists())

    def transaction_fixture(self):
        self.node.STATE=self.root/'state';self.node.STATE.mkdir(mode=0o700)
        self.node.RUNTIME=self.root/'runtime';self.node.RUNTIME.mkdir(mode=0o700)
        self.node.JOURNAL=self.node.STATE/'transaction.json'
        self.node.JOURNAL.write_text(json.dumps(self.record));self.node.JOURNAL.chmod(0o600)
        for name in ['node.env','tls.key','ca.crt']:
            path=self.node.STATE/name;path.write_bytes(b'private-demo-material');path.chmod(0o600)

    def test_ready_configuration_finalizes_only_after_controller_commit(self):
        self.transaction_fixture()
        old=self.node.JOURNAL.read_bytes();crypto=(self.fixture.pki/'private/alice.key').read_bytes()
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run') as run:
            result=self.module.apply(self.request(protocol='tcp',ovpn_port=443))
            self.assertEqual(result['state'],'ready');self.assertEqual(self.node.JOURNAL.read_bytes(),old)
            self.assertIn(b'proto tcp-server',self.server.read_bytes())
            self.assertEqual((self.fixture.pki/'private/alice.key').read_bytes(),crypto)
            self.module.finalize(result['transaction_id'])
            self.assertEqual(json.loads(self.node.JOURNAL.read_text())['configuration']['ovpn_port'],443)
            self.assertEqual(self.module.active_record()['state'],'complete')
            self.assertEqual(run.call_args_list[0].args[0],['systemctl','restart','openvpn-server@server'])

    def test_ready_configuration_rollback_restores_headers_and_original_journal(self):
        self.transaction_fixture()
        paths=[self.server,self.template,self.fixture.profile,self.module.NETWORK,self.node.JOURNAL]
        originals={path:path.read_bytes() for path in paths}
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run'):
            result=self.module.apply(self.request(tunnel_address='vpn.example.com'))
            self.assertFalse(result['vpn_restarted'])
            self.module.recover(result['transaction_id'])
        self.assertEqual({path:path.read_bytes() for path in paths},originals)

    def test_operator_change_after_ready_is_preserved_before_any_recovery_restart(self):
        self.transaction_fixture()
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run') as run:
            result=self.module.apply(self.request(tunnel_address='vpn.example.com'))
            self.fixture.profile.write_bytes(b'operator changed profile')
            run.reset_mock()
            with self.assertRaises(ValueError):self.module.recover(result['transaction_id'])
            self.assertEqual(run.call_count,0)
        self.assertEqual(self.fixture.profile.read_bytes(),b'operator changed profile')

    def test_interrupted_finalization_rolls_forward_after_controller_commit(self):
        self.assert_interrupted_finalization('committed')

    def test_interrupted_finalization_decision_also_rolls_forward(self):
        self.assert_interrupted_finalization('committing')

    def assert_interrupted_finalization(self,phase_name):
        self.transaction_fixture()
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run'):
            result=self.module.apply(self.request(protocol='tcp',ovpn_port=443))
            with patch.dict(os.environ,{'PVNETWORK_NODE_CONFIG_TEST_FAIL_AT':phase_name}):
                with self.assertRaises(ValueError):self.module.finalize(result['transaction_id'])
            recovered=self.module.recover(result['transaction_id'])
        self.assertEqual(recovered['state'],'complete')
        self.assertEqual(json.loads(self.node.JOURNAL.read_text())['configuration']['ovpn_port'],443)
        self.assertIn(b'port 443',self.server.read_bytes())

    def test_precommit_failure_phases_restore_exact_original_files(self):
        self.transaction_fixture()
        paths=[self.server,self.template,self.fixture.profile,self.module.NETWORK,self.node.JOURNAL]
        originals={path:path.read_bytes() for path in paths}
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run',return_value='41'):
            for phase_name in ['prepared','rules_added','switching','switched','restarting','ready']:
                with self.subTest(phase=phase_name),patch.dict(os.environ,{'PVNETWORK_NODE_CONFIG_TEST_FAIL_AT':phase_name}):
                    with self.assertRaises(ValueError):self.module.apply(self.request(protocol='tcp',ovpn_port=443))
                self.module.recover()
                self.assertEqual({path:path.read_bytes() for path in paths},originals)
                self.assertEqual(self.module.active_record()['state'],'rolled_back')

    def test_unknown_controller_decision_at_ready_is_preserved(self):
        self.transaction_fixture()
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run') as run:
            result=self.module.apply(self.request(tunnel_address='vpn.example.com'))
            changed=self.fixture.profile.read_bytes();run.reset_mock()
            with self.assertRaises(ValueError):self.module.recover()
            self.assertEqual(self.fixture.profile.read_bytes(),changed)
            self.assertEqual(run.call_count,0)
            self.module.recover(result['transaction_id'])

    def test_pending_configuration_blocks_other_mutations(self):
        self.transaction_fixture()
        path=self.node.STATE/'configuration-transaction.json';path.write_text(json.dumps({'state':'ready'}));path.chmod(0o600)
        with self.assertRaises(ValueError):self.node.require_configuration_complete()
        path.write_text(json.dumps({'state':'complete'}))
        self.node.require_configuration_complete()

    def test_repeated_controller_operation_id_returns_ready_without_reapplying(self):
        self.transaction_fixture();request=self.request(tunnel_address='vpn.example.com')
        with patch.object(self.module,'take_backup',return_value={'verified':True}) as backup,patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run'):
            first=self.module.apply(request,transaction_id='b'*24)
            second=self.module.apply(request,transaction_id='b'*24)
            self.assertEqual(first['transaction_id'],second['transaction_id'])
            self.assertEqual(second['state'],'ready');self.assertEqual(backup.call_count,1)
            with self.assertRaises(ValueError):self.module.apply(self.request(tunnel_address='other.example.com'),transaction_id='b'*24)
            self.module.recover(first['transaction_id'])

    def test_ready_recovery_uses_authenticated_controller_commit_decision(self):
        self.transaction_fixture()
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run'),patch.object(self.module,'controller_decision',return_value='finalize'):
            self.module.apply(self.request(tunnel_address='vpn.example.com'))
            result=self.module.recover()
        self.assertEqual(result['state'],'complete')
        self.assertEqual(json.loads(self.node.JOURNAL.read_text())['configuration']['tunnel_address'],'vpn.example.com')

    def test_finalization_refuses_profile_reverted_during_ready(self):
        self.transaction_fixture();original=self.fixture.profile.read_bytes()
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run'):
            result=self.module.apply(self.request(tunnel_address='vpn.example.com'))
            self.fixture.profile.write_bytes(original)
            with self.assertRaises(ValueError):self.module.finalize(result['transaction_id'])
            self.assertEqual(self.module.active_record()['state'],'ready')

    def test_committed_recovery_starts_missing_owned_VPN_before_snapshot(self):
        self.transaction_fixture()
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run',return_value='41') as run:
            result=self.module.apply(self.request(protocol='tcp',ovpn_port=443))
            with patch.dict(os.environ,{'PVNETWORK_NODE_CONFIG_TEST_FAIL_AT':'committing'}):
                with self.assertRaises(ValueError):self.module.finalize(result['transaction_id'])
            run.reset_mock();run.return_value='0'
            self.module.recover()
            commands=[call.args[0] for call in run.call_args_list]
            self.assertIn(['systemctl','start','openvpn-server@server'],commands)

    def test_adopted_rollback_PID_refresh_keeps_durable_snapshot_versions(self):
        self.transaction_fixture()
        self.record['adopted']={'pid':'41'};self.node.JOURNAL.write_text(json.dumps(self.record))
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',side_effect=[{'pid':'41'},{'pid':'42'},{'pid':'43'}]),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run',return_value='42'):
            result=self.module.apply(self.request(protocol='tcp',ovpn_port=443))
            self.module.recover(result['transaction_id'])
        installed=json.loads(self.node.JOURNAL.read_text())
        self.assertEqual(installed['adopted']['pid'],'43')
        self.assertEqual(installed['configuration']['ovpn_port'],1194)
        value=self.module.active_record();self.module.validate_transaction(value,result['transaction_id'])

    def test_tampered_recovery_target_outside_configuration_scope_is_preserved(self):
        self.transaction_fixture();foreign=self.root/'foreign-service';foreign.write_bytes(b'operator service')
        with patch.object(self.module,'take_backup',return_value={'verified':True}),patch.object(self.module,'vpn_snapshot',return_value={'pid':'41'}),patch.object(self.module,'add_rules'),patch.object(self.module,'remove_rules'),patch.object(self.node,'run') as run:
            result=self.module.apply(self.request(tunnel_address='vpn.example.com'))
            value=self.module.active_record();item=value['files'][0]
            item['path']=str(foreign);item['previous_sha256']=hashlib.sha256(foreign.read_bytes()).hexdigest()
            stage=Path(value['stage']);self.node.private(stage/item['previous'],foreign.read_bytes())
            self.node.private(self.module.journal_path(),json.dumps(value))
            run.reset_mock()
            with self.assertRaises(ValueError):self.module.recover(result['transaction_id'])
            self.assertEqual(run.call_count,0)
        self.assertEqual(foreign.read_bytes(),b'operator service')


if __name__=='__main__':unittest.main()
