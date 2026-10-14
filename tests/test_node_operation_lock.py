import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class NodeOperationLockTests(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('operation_lock_node',ROOT/'scripts/pvnetwork_node_install.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def test_linked_state_is_refused_without_changing_foreign_directory(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);foreign=root/'foreign';foreign.mkdir();foreign.chmod(0o755)
            state=root/'state';state.symlink_to(foreign,target_is_directory=True)
            with patch.object(module,'STATE',state):
                with self.assertRaises(ValueError):
                    with module.operation_lock(): pass
            self.assertEqual(foreign.stat().st_mode&0o777,0o755)
            self.assertFalse((foreign/'install.lock').exists())
            with patch.object(module,'STATE',state),patch.object(module,'JOURNAL',root/'missing.json'),patch.object(module.os,'geteuid',return_value=0),patch('sys.argv',['node-install','--action','status']):
                with self.assertRaises((ValueError,OSError)):module.main()
            self.assertEqual(foreign.stat().st_mode&0o777,0o755)
            self.assertFalse((foreign/'install.lock').exists())

    @unittest.skipUnless(hasattr(os,'geteuid') and os.geteuid()==0,'private state fixtures run in the isolated root gate')
    def test_symlink_and_hardlinked_lock_preserve_foreign_file(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);state=root/'state';state.mkdir(mode=0o700)
            foreign=root/'operator';foreign.write_bytes(b'preserve');foreign.chmod(0o644)
            lock=state/'install.lock'
            for hardlink in [False,True]:
                if hardlink: os.link(foreign,lock)
                else: lock.symlink_to(foreign)
                with patch.object(module,'STATE',state):
                    with self.assertRaises(ValueError):
                        with module.operation_lock(): pass
                self.assertEqual(foreign.read_bytes(),b'preserve')
                self.assertEqual(foreign.stat().st_mode&0o777,0o644)
                lock.unlink()

    @unittest.skipUnless(hasattr(os,'geteuid') and os.geteuid()==0,'private state fixtures run in the isolated root gate')
    def test_shared_write_state_is_refused_before_permission_changes(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state';state.mkdir();state.chmod(0o777)
            with patch.object(module,'STATE',state):
                with self.assertRaises(ValueError):
                    with module.operation_lock(): pass
            self.assertEqual(state.stat().st_mode&0o777,0o777)
            self.assertFalse((state/'install.lock').exists())

    @unittest.skipUnless(hasattr(os,'geteuid') and os.geteuid()==0,'private state fixtures run in the isolated root gate')
    def test_private_lock_excludes_concurrent_operation_and_can_be_reused(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/'state'
            with patch.object(module,'STATE',state):
                with module.operation_lock():
                    self.assertEqual(state.stat().st_mode&0o777,0o700)
                    self.assertEqual((state/'install.lock').stat().st_mode&0o777,0o600)
                    with self.assertRaises(BlockingIOError):
                        with module.operation_lock(): pass
                with module.operation_lock(): pass


if __name__=='__main__':unittest.main()
