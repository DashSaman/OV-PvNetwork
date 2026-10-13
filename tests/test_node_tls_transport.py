import tempfile
from pathlib import Path
from unittest import TestCase, mock

from backend.node.requests import NodeRequests
from backend.node import tls


class NativeTransportTests(TestCase):
    def test_adopted_unchanged_credential_cannot_use_http_after_ca_folder_loss(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(tls,'ROOT',Path(directory)), mock.patch.object(tls,'binding',return_value={'ca_sha256':'0'*64,'credential_sha256':'1'*64}):
            with self.assertRaisesRegex(ValueError,'trust'):
                NodeRequests('node.example.com',9443,'unchanged-legacy-credential')

    def test_binding_is_durable_owned_metadata_without_plaintext_credential(self):
        from sqlalchemy import create_engine
        from backend.node import tls_binding
        engine=create_engine('sqlite://')
        with mock.patch.object(tls_binding,'database',return_value=engine):
            self.assertIsNone(tls_binding.lookup('demo'))
            tls_binding.store('demo','node.example.com',9443,'0'*64,'unchanged-demo-credential')
            stored=tls_binding.lookup('demo')
            self.assertEqual(stored['port'],9443)
            self.assertNotIn('unchanged-demo-credential',str(stored))
            self.assertEqual(len(stored['credential_sha256']),64)
        engine.dispose()

    def test_native_key_cannot_fall_back_when_pin_is_missing(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(tls, 'ROOT', Path(directory)):
            with self.assertRaisesRegex(ValueError, 'trust'):
                NodeRequests('node.example.com', 9443, 'pvn_tls_v1_demo')

    def test_native_tls_never_redirects_or_disables_verification(self):
        with mock.patch.object(tls, 'trust_path', return_value='/private/node-ca.pem'), mock.patch('backend.node.requests.requests.get') as get:
            client=NodeRequests('node.example.com',9443,'pvn_tls_v1_demo')
            get.return_value.json.return_value={'success':True}
            self.assertTrue(client.check_node())
            self.assertEqual(get.call_args.args[0], 'https://node.example.com:9443/sync/status')
            self.assertEqual(get.call_args.kwargs['verify'], '/private/node-ca.pem')
            self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_legacy_ipv6_uses_bracketed_authority(self):
        with mock.patch('backend.node.requests.requests.get') as get:
            get.return_value.json.return_value={'success':True}
            self.assertTrue(NodeRequests('::1',9090,'legacy-demo').check_node())
            self.assertEqual(get.call_args.args[0], 'http://[::1]:9090/sync/status')
