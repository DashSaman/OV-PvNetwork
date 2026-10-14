import importlib.util
import os
from pathlib import Path
import sys
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

    def test_conflicting_own_profile_or_stale_journal_refuses_before_any_write(self):
        original=self.server.read_bytes();self.fixture.profile.write_bytes(self.fixture.content('bob'))
        with self.assertRaises(ValueError):self.module.prepare(self.record,self.request(ovpn_port=443))
        self.assertEqual(self.server.read_bytes(),original)
        self.fixture.profile.write_bytes(self.fixture.content('alice'))
        self.record['configuration']['ovpn_port']=1195
        with self.assertRaises(ValueError):self.module.prepare(self.record,self.request(ovpn_port=443))
        self.assertEqual(self.server.read_bytes(),original)


if __name__=='__main__':unittest.main()
