import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]


class LifecycleTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('pvnetwork_lifecycle_tx',ROOT/'scripts/pvnetwork_lifecycle.py')
        cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)

    def test_failed_build_never_switches_active_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old';old.mkdir();pointer=root/'panel';pointer.symlink_to(old,target_is_directory=True)
            candidate=root/'new';candidate.mkdir()
            def build():raise RuntimeError('build failure')
            with self.assertRaises(RuntimeError):self.module.commit_release(pointer,candidate,build,lambda:None,lambda:None)
            self.assertEqual(pointer.resolve(),old)

    def test_failed_post_switch_health_restores_previous_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old';old.mkdir();pointer=root/'panel';pointer.symlink_to(old,target_is_directory=True)
            new=root/'new';new.mkdir();events=[]
            def verify():
                if pointer.resolve()==new:raise RuntimeError('bad health')
                events.append('recovery verified')
            with self.assertRaises(RuntimeError):self.module.commit_release(pointer,new,lambda:None,lambda:events.append('restart'),verify)
            self.assertEqual(pointer.resolve(),old)
            self.assertEqual(events,['restart','restart','recovery verified'])

    def test_success_switches_only_after_build_and_preflight(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old';old.mkdir();pointer=root/'panel';pointer.symlink_to(old,target_is_directory=True)
            new=root/'new';new.mkdir();events=[]
            def build():self.assertEqual(pointer.resolve(),old);events.append('prepared')
            def verify():self.assertEqual(pointer.resolve(),new);events.append('verified')
            self.module.commit_release(pointer,new,build,lambda:events.append('restart'),verify)
            self.assertEqual(events,['prepared','restart','verified'])
