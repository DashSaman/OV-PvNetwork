import importlib.util
from pathlib import Path
import subprocess
import os
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ClientProfileIdentityTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('profile_identity', ROOT / 'node-agent/core/service/client_profile.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pki = self.root / 'pki'
        self.pki.mkdir()
        (self.pki / 'issued').mkdir()
        (self.pki / 'private').mkdir()
        self.openssl('req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-days', '2', '-subj', '/CN=DemoCA', '-keyout', 'ca.key', '-out', 'pki/ca.crt')
        self.client('alice', '01')
        self.client('bob', '02')
        (self.pki / 'index.txt').write_text('V\t351231000000Z\t\t01\tunknown\t/CN=alice\nV\t351231000000Z\t\t02\tunknown\t/CN=bob\n')
        self.profile = self.root / 'alice.ovpn'
        self.profile.write_bytes(self.content('alice'))
        self.profile.chmod(0o600)

    def openssl(self, *args):
        result = subprocess.run(['openssl', *args], cwd=self.root, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, 'demo certificate fixture generation failed')

    def client(self, name, serial):
        self.openssl('req', '-new', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-subj', '/CN='+name, '-keyout', 'pki/private/'+name+'.key', '-out', name+'.csr')
        self.openssl('x509', '-req', '-in', name+'.csr', '-CA', 'pki/ca.crt', '-CAkey', 'ca.key', '-set_serial', '0x'+serial, '-days', '2', '-out', 'pki/issued/'+name+'.crt')

    def content(self, name):
        data = b'client\nremote node.example.com 1194\nproto udp\n'
        for tag, path in [('ca', 'ca.crt'), ('cert', 'issued/'+name+'.crt'), ('key', 'private/'+name+'.key')]:
            data += ('<'+tag+'>\n').encode() + (self.pki/path).read_bytes() + ('</'+tag+'>\n').encode()
        return data + b'<tls-crypt-v2>\nDEMO OPAQUE WRAPPED MATERIAL\n</tls-crypt-v2>\n'

    def test_real_certificate_identity_and_header_update_preserve_inline_bytes(self):
        original = self.profile.read_bytes()
        self.module.verify_profile(self.profile, 'alice', self.pki)
        changed = self.module.update_endpoint(original, 'vpn.example.com', 443, 'tcp')
        self.assertIn(b'remote vpn.example.com 443\nproto tcp-client\n', changed)
        self.assertEqual(changed[changed.index(b'<ca>'):], original[original.index(b'<ca>'):])

    def test_other_clients_profile_and_mismatched_key_are_refused(self):
        self.profile.write_bytes(self.content('bob'))
        with self.assertRaises(ValueError): self.module.verify_profile(self.profile, 'alice', self.pki)
        self.profile.write_bytes(self.content('alice').replace((self.pki/'private/alice.key').read_bytes(), (self.pki/'private/bob.key').read_bytes()))
        with self.assertRaises(ValueError): self.module.verify_profile(self.profile, 'alice', self.pki)

    def test_revoked_or_reissued_certificate_is_refused(self):
        index = self.pki/'index.txt'
        index.write_text(index.read_text().replace('V\t351231000000Z\t\t01', 'R\t351231000000Z\t261014000000Z\t01'))
        with self.assertRaises(ValueError): self.module.verify_profile(self.profile, 'alice', self.pki)
        index.write_text('V\t351231000000Z\t\t03\tunknown\t/CN=alice\n')
        self.client('alice', '03')
        with self.assertRaises(ValueError): self.module.verify_profile(self.profile, 'alice', self.pki)

    def test_foreign_ca_duplicate_blocks_and_symlink_are_refused(self):
        original = self.profile.read_bytes()
        self.profile.write_bytes(original + b'<cert>\n'+(self.pki/'issued/alice.crt').read_bytes()+b'</cert>\n')
        with self.assertRaises(ValueError): self.module.verify_profile(self.profile, 'alice', self.pki)
        self.profile.write_bytes(original)
        self.openssl('req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-days', '2', '-subj', '/CN=ForeignCA', '-keyout', 'foreign.key', '-out', 'foreign.crt')
        self.profile.write_bytes(original.replace((self.pki/'ca.crt').read_bytes(), (self.root/'foreign.crt').read_bytes()))
        with self.assertRaises(ValueError): self.module.verify_profile(self.profile, 'alice', self.pki)
        self.profile.unlink();self.profile.symlink_to(self.root/'foreign.crt')
        with self.assertRaises(ValueError): self.module.verify_profile(self.profile, 'alice', self.pki)

    def test_ambiguous_endpoint_and_inline_connection_are_refused(self):
        for suffix in [b'remote other.example.com 443\n', b'<connection>\nremote other.example.com 443\n</connection>\n', b'proto tcp-client\n']:
            with self.assertRaises(ValueError): self.module.update_endpoint(self.content('alice')+suffix, 'vpn.example.com', 443, 'tcp')

    def test_endpoint_only_preserves_equivalent_protocol_and_unchanged_header_spacing(self):
        original=self.content('alice').replace(b'proto udp\n',b'proto\ttcp\n').replace(b'remote node.example.com 1194\n',b'remote\tnode.example.com\t1194\n')
        self.assertEqual(self.module.update_endpoint(original,'node.example.com',1194,'tcp'),original)
        changed=self.module.update_endpoint(original,'vpn.example.com',1194,'tcp')
        self.assertIn(b'proto\ttcp\n',changed)

    def builder(self):
        # Relocate fixed production paths only in this disposable test script.
        source = (ROOT/'scripts/pvnetwork-build-client-profile').read_text()
        source = source.replace('BASE="/etc/openvpn/server"', 'BASE="'+str(self.root)+'"')
        source = source.replace('EASY="$BASE/easy-rsa"', 'EASY="$BASE"')
        source = source.replace('/root/', str(self.root)+'/')
        source = source.replace('/etc/openvpn/ccd', str(self.root/'compat-ccd'))
        source = source.replace('/opt/pvnetwork-node/core/service/client_profile.py', str(ROOT/'node-agent/core/service/client_profile.py'))
        target = self.root/'builder.sh';target.write_text(source)
        return subprocess.run(['bash', str(target), 'alice'], capture_output=True, timeout=15)

    def test_builder_refuses_foreign_or_revoked_cached_profile_before_ccd_changes(self):
        for revoked in [False, True]:
            if revoked:
                self.profile.write_bytes(self.content('alice'))
                index = self.pki/'index.txt';index.write_text(index.read_text().replace('V\t351231000000Z\t\t01', 'R\t351231000000Z\t261014000000Z\t01'))
            else: self.profile.write_bytes(self.content('bob'))
            original = self.profile.read_bytes()
            result = self.builder()
            self.assertNotEqual(result.returncode, 0, 'invalid cached profile was accepted')
            self.assertEqual(self.profile.read_bytes(), original)
            self.assertFalse((self.root/'ccd').exists())

    def test_builder_preserves_existing_customer_ccd_on_repeat(self):
        ccd = self.root/'ccd';ccd.mkdir();custom = ccd/'alice'
        custom.write_text('ifconfig-push 10.8.0.44 255.255.255.0\n')
        original = custom.read_bytes()
        result = self.builder()
        self.assertEqual(result.returncode, 0, 'verified repeat profile failed')
        self.assertEqual(custom.read_bytes(), original)

    def test_download_validates_existing_profile_without_reactivating_customer(self):
        code = '''
import asyncio,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'node-agent')
from core.service import user_managment as m
m._PVNETWORK_PROFILE_DIR=sys.argv[1];m._PVNETWORK_EASYRSA_DIR=sys.argv[1]
profile=Path(sys.argv[1])/'alice.ovpn'
with patch.object(m,'create_user_on_server') as create:
 assert asyncio.run(m.download_ovpn_file('alice'))==str(profile)
 foreign=profile.read_bytes().replace((Path(sys.argv[1])/'pki/issued/alice.crt').read_bytes(),(Path(sys.argv[1])/'pki/issued/bob.crt').read_bytes())
 profile.write_bytes(foreign)
 assert asyncio.run(m.download_ovpn_file('alice')) is None
 assert create.call_count==0
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.root)], cwd=ROOT, env={**os.environ, 'API_KEY':'ci-node-profile-identity-not-production'}, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))


if __name__ == '__main__': unittest.main()
