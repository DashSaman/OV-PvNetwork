"""Deployment source is self-contained and checked before remote execution."""
import io
import tarfile
import unittest


class NativeNodeBundleTests(unittest.TestCase):
    def test_fresh_controller_builds_bundle_without_installed_local_node(self):
        from backend.node.deploy import build_native_node_bundle
        payload,checksum=build_native_node_bundle()
        import hashlib
        self.assertEqual(hashlib.sha256(payload).hexdigest(),checksum)
        with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
            names=set(archive.getnames())
            self.assertIn('node-agent/core/routers/router.py',names)
            self.assertIn('node-agent/LICENSE',names)
            self.assertIn('scripts/pvnetwork_node_install.py',names)
            self.assertIn('ops/toolchain.json',names)
            self.assertFalse(any(m.issym() or m.islnk() or '..' in m.name.split('/') for m in archive.getmembers()))
            self.assertFalse(any(name.endswith(('.env','.key','.pem','.crt','.db','.ovpn')) for name in names))

    def test_bundle_runtime_uses_native_paths_and_tls(self):
        from backend.node.deploy import build_native_node_bundle
        payload,_=build_native_node_bundle()
        with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
            main=archive.extractfile('node-agent/main.py').read().decode()
            self.assertIn('ssl_certfile',main);self.assertIn('ssl_keyfile',main)
            self.assertNotIn('reload=True',main)
            install=archive.extractfile('scripts/pvnetwork_node_install.py').read().decode()
            self.assertIn('/opt/pvnetwork-node',install);self.assertIn('/etc/pvnetwork-node',install)

    def test_source_bundle_has_no_private_controller_defaults(self):
        from backend.node.deploy import build_native_node_bundle
        payload,_=build_native_node_bundle()
        with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
            module=archive.extractfile('node-agent/core/routers/domain_history.py').read().decode()
            self.assertIn('settings.panel_url',module)
            self.assertNotIn('https://open',module)

    def test_ignored_runtime_files_are_never_collected_from_the_agent_tree(self):
        from backend.node import deploy
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        payload,_=deploy.build_native_node_bundle()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:archive.extractall(root,filter='data')
            (root/'node-agent/.env.backup').write_text('API_KEY=ci-private-fixture-not-production')
            (root/'node-agent/usage.db').write_bytes(b'ci-private-runtime-not-source')
            with patch.object(deploy,'__file__',str(root/'backend/node/deploy.py')):
                clean,_=deploy.build_native_node_bundle()
            with tarfile.open(fileobj=io.BytesIO(clean),mode='r:gz') as archive:
                self.assertNotIn('node-agent/.env.backup',archive.getnames())
                self.assertNotIn('node-agent/usage.db',archive.getnames())
