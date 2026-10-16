"""Private archives remain bound to the exact registered node identity."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


@unittest.skipUnless(os.name=='posix','private POSIX storage required')
class NodeArchiveStoreTests(unittest.TestCase):
    def setUp(self):
        from backend.node import archive_store
        self.store=archive_store;self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'archives'
        self.override=patch.object(self.store,'ROOT',self.root);self.override.start()
        self.node=SimpleNamespace(id=7,address='node.example.invalid',port=9443,key='private-demo-node-key')

    def tearDown(self):
        self.override.stop();self.temp.cleanup()

    def save(self,content=b'private archive fixture'):
        entry=self.store.create(self.node,'upload')
        self.store.write(entry,[content],limit=1000)
        return entry

    def test_sealed_private_archive_checks_node_bytes_and_expiry(self):
        entry=self.save();saved=self.store.load(entry['id'],self.node)
        self.assertEqual(saved['sha256'],hashlib.sha256(b'private archive fixture').hexdigest())
        self.assertEqual(self.root.stat().st_mode&0o777,0o700)
        self.assertEqual(self.store.path(saved).stat().st_mode&0o777,0o600)
        with self.store.open_verified(saved) as handle:self.assertEqual(handle.read(),b'private archive fixture')
        for field,value in [('id',8),('address','other.example.invalid'),('port',9090),('key','rotated-key')]:
            changed=SimpleNamespace(**vars(self.node));setattr(changed,field,value)
            with self.subTest(field=field),self.assertRaises(ValueError):self.store.load(entry['id'],changed)
        with patch.object(self.store.time,'time',return_value=entry['expires_at']+1),self.assertRaises(ValueError):self.store.load(entry['id'],self.node)
        self.assertNotIn(self.node.key,(self.root/entry['id']/'metadata.json').read_text())

    def test_oversize_input_is_never_sealed_or_downloadable(self):
        entry=self.store.create(self.node,'upload')
        with self.assertRaises(ValueError):self.store.write(entry,[b'123',b'456'],limit=5)
        with self.assertRaises(ValueError):self.store.load(entry['id'],self.node)
        self.assertFalse(self.store.path(entry).exists())

    def test_tampered_link_permissions_and_bytes_are_preserved_and_refused(self):
        entry=self.save();file=self.store.path(entry);file.chmod(0o644)
        with self.assertRaises(ValueError):self.store.open_verified(entry)
        file.chmod(0o600);file.write_bytes(b'operator changed content')
        with self.assertRaises(ValueError):self.store.open_verified(entry)
        with patch.object(self.store.time,'time',return_value=entry['expires_at']+1):self.store.cleanup()
        self.assertEqual(file.read_bytes(),b'operator changed content')
        file.unlink();file.symlink_to(Path(self.temp.name)/'foreign')
        with self.assertRaises(ValueError):self.store.open_verified(entry)

    def test_expiry_cleans_only_unchanged_owned_receipts(self):
        entry=self.save();foreign=self.root/'operator-file';foreign.write_text('preserve')
        with patch.object(self.store.time,'time',return_value=entry['expires_at']+1):self.store.cleanup()
        self.assertFalse((self.root/entry['id']).exists());self.assertEqual(foreign.read_text(),'preserve')

    def test_traversal_symlink_root_and_capacity_refused(self):
        with self.assertRaises(ValueError):self.store.load('../foreign',self.node)
        self.root.symlink_to(self.temp.name,target_is_directory=True)
        with self.assertRaises(ValueError):self.store.create(self.node,'upload')
        self.root.unlink()
        with patch.object(self.store,'MAX_ENTRIES',1):
            self.save()
            with self.assertRaises(ValueError):self.store.create(self.node,'upload')

    def test_full_archive_byte_budget_keeps_interrupted_recovery_available(self):
        with patch.object(self.store,'MAX_BYTES',self.store.LIMIT):
            self.save()
            with self.assertRaises(ValueError):self.store.create(self.node,'backup')
            entry=self.store.create(self.node,'recovery')
            self.assertEqual(entry['kind'],'recovery');self.assertFalse(self.store.path(entry).exists())
