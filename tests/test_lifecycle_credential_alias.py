"""Actual root-owned POSIX compatibility alias, never an operational key."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux' and getattr(os, 'geteuid', lambda: -1)() == 0,
                     'Real key-link ownership fixtures run in the explicit root Linux CI gate')
class LifecycleCredentialAliasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pvnetwork-key-alias-', dir='/root')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.app = root / 'app'
        (self.app / 'data').mkdir(parents=True, mode=0o700)
        self.state = root / 'state'
        self.state.mkdir(mode=0o700)
        legacy = root / 'legacy'
        legacy.mkdir(mode=0o700)
        self.legacy = legacy / 'anyconnect-credential-fernet.key'
        self.key = Fernet.generate_key()
        self.legacy.write_bytes(self.key + b'\n')
        self.legacy.chmod(0o600)
        self.canonical = self.state / 'anyconnect-credential-fernet.key'
        self.canonical.symlink_to(self.legacy)
        self.archive = root / 'runtime.tar.gz'
        spec = importlib.util.spec_from_file_location('pvnetwork_credential_alias_test', ROOT / 'scripts/pvnetwork_lifecycle.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        patches = [mock.patch.object(self.module, 'APP', self.app),
                   mock.patch.object(self.module, 'STATE', self.state),
                   mock.patch.object(self.module, 'LEGACY_CREDENTIAL_KEY', self.legacy, create=True)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.environment = {'DATABASE_URL': 'sqlite:///' + str(self.app / 'data/demo.db')}

    def snapshot(self):
        return self.module.snapshot_runtime_files(self.archive, self.environment)

    def test_actual_alias_backup_and_restore_preserve_link_and_decryption(self):
        ciphertext = Fernet(self.key).encrypt(b'PVNetwork synthetic credential')
        before_link = (self.canonical.lstat().st_ino, os.readlink(self.canonical))
        expected = self.snapshot()
        with tarfile.open(self.archive) as archive:
            member = archive.getmember('state/anyconnect-credential-fernet.key')
            self.assertTrue(member.isfile())
            self.assertEqual(hashlib.sha256(archive.extractfile(member).read()).hexdigest(), expected[member.name])
        self.legacy.write_bytes(Fernet.generate_key() + b'\n')
        self.module.restore_runtime_files(self.archive, expected)
        self.assertEqual((self.canonical.lstat().st_ino, os.readlink(self.canonical)), before_link)
        self.assertEqual(Fernet(self.canonical.read_bytes().strip()).decrypt(ciphertext), b'PVNetwork synthetic credential')
        self.assertEqual(self.legacy.stat().st_mode & 0o777, 0o600)

    def test_regular_canonical_key_keeps_existing_restore_behavior(self):
        self.canonical.unlink()
        self.canonical.write_bytes(self.key)
        self.canonical.chmod(0o600)
        expected = self.snapshot()
        self.canonical.write_bytes(Fernet.generate_key())
        self.module.restore_runtime_files(self.archive, expected)
        self.assertFalse(self.canonical.is_symlink())
        self.assertEqual(hashlib.sha256(self.canonical.read_bytes()).hexdigest(), hashlib.sha256(self.key).hexdigest())

    def test_verified_restore_repairs_missing_or_empty_target_without_replacing_link(self):
        expected = self.snapshot()
        before = (self.canonical.lstat().st_ino, os.readlink(self.canonical))
        for missing in [True, False]:
            if missing:
                self.legacy.unlink()
            else:
                self.legacy.write_bytes(b'')
            with self.subTest(missing=missing):
                self.module.restore_runtime_files(self.archive, expected)
                self.assertEqual((self.canonical.lstat().st_ino, os.readlink(self.canonical)), before)
                self.assertEqual(hashlib.sha256(self.legacy.read_bytes().strip()).hexdigest(), hashlib.sha256(self.key).hexdigest())

    def test_arbitrary_redirected_alias_is_refused_without_reading_it(self):
        other = self.legacy.with_name('unrelated.key')
        other.write_bytes(b'untouched demo bytes')
        other.chmod(0o600)
        self.canonical.unlink()
        self.canonical.symlink_to(other)
        with self.assertRaises(ValueError):
            self.snapshot()
        self.assertEqual(other.read_bytes(), b'untouched demo bytes')

    def test_linked_legacy_target_is_refused(self):
        other = self.legacy.with_name('other.key')
        self.legacy.rename(other)
        self.legacy.symlink_to(other)
        with self.assertRaises(ValueError):
            self.snapshot()

    def test_missing_target_is_refused(self):
        self.legacy.unlink()
        with self.assertRaises(ValueError):
            self.snapshot()

    def test_unsafe_alias_target_and_parent_permissions_are_refused(self):
        for target, mode in [(self.legacy, 0o644), (self.legacy.parent, 0o770), (self.state, 0o777)]:
            previous = target.stat().st_mode & 0o777
            target.chmod(mode)
            with self.subTest(target=target.name), self.assertRaises(ValueError):
                self.snapshot()
            target.chmod(previous)

    def test_non_root_link_or_target_owner_is_refused(self):
        for target in [self.canonical, self.legacy, self.legacy.parent, self.state]:
            os.lchown(target, 12345, 12345)
            try:
                with self.assertRaises(ValueError):
                    self.snapshot()
            finally:
                os.lchown(target, 0, 0)

    def test_changed_alias_is_refused_before_restore_writes(self):
        expected = self.snapshot()
        other = self.legacy.with_name('unrelated.key')
        other.write_bytes(b'untouched demo bytes')
        other.chmod(0o600)
        self.canonical.unlink()
        self.canonical.symlink_to(other)
        with self.assertRaises(ValueError):
            self.module.restore_runtime_files(self.archive, expected)
        self.assertEqual(other.read_bytes(), b'untouched demo bytes')

    def test_custom_configured_path_stays_refused(self):
        with self.assertRaisesRegex(ValueError, 'custom credential key location'):
            self.module.runtime_files({**self.environment, 'PVNETWORK_ANYCONNECT_CREDENTIAL_KEY_FILE': str(self.legacy)})


if __name__ == '__main__':
    unittest.main()
