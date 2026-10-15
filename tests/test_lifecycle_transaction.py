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

    def test_only_exact_additive_binding_revision_is_allowlisted(self):
        m=self.module
        with mock.patch.object(m,'_schema_head',return_value='i1b2c3d4e5f6'),mock.patch.object(m,'_db_head',return_value='h0a1b2c3d4e5'):
            plan=m.migration_plan(ROOT,{})
        self.assertEqual(plan['from'],'h0a1b2c3d4e5')
        self.assertEqual(plan['to'],'i1b2c3d4e5f6')
        self.assertTrue(m.schema_compatible_with_previous('h0a1b2c3d4e5','i1b2c3d4e5f6'))
        self.assertFalse(m.schema_compatible_with_previous('i1b2c3d4e5f6','h0a1b2c3d4e5'))
        with mock.patch.object(m,'_schema_head',return_value='foreign_head'),mock.patch.object(m,'_db_head',return_value='h0a1b2c3d4e5'),self.assertRaisesRegex(ValueError,'schema-changing'):
            m.migration_plan(ROOT,{})

    def test_changed_revision_parent_is_refused_before_database_operation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'backend/alembic/versions';p.mkdir(parents=True)
            (p/'i1b2c3d4e5f6_native_node_tls_binding.py').write_text("revision='i1b2c3d4e5f6'\ndown_revision='foreign'\n")
            with mock.patch.object(self.module,'_schema_head',return_value='i1b2c3d4e5f6'),mock.patch.object(self.module,'_db_head',return_value='h0a1b2c3d4e5'),self.assertRaisesRegex(ValueError,'parent'):
                self.module.migration_plan(root,{})
