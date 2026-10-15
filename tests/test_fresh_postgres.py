"""Real empty PostgreSQL initialization; only a dedicated loopback QA service."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest

from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]
QA_URL=os.environ.get('PVNETWORK_TEST_POSTGRES_URL')


@unittest.skipUnless(QA_URL,'NOT TESTED: dedicated loopback PostgreSQL QA service absent')
class FreshPostgresTests(unittest.TestCase):
    def setUp(self):
        self.url=make_url(QA_URL)
        if self.url.host not in {'127.0.0.1','localhost','pvnetwork-test-postgres'}:raise ValueError('fresh DB QA is restricted to the dedicated loopback test service')
        self.name='pvnetwork_test_'+secrets.token_hex(10)
        self.admin=create_engine(self.url,isolation_level='AUTOCOMMIT')
        with self.admin.connect() as c:c.execute(text('CREATE DATABASE "'+self.name+'"'))
        self.target=self.url.set(database=self.name);self.engine=create_engine(self.target)

    def tearDown(self):
        self.engine.dispose()
        with self.admin.connect() as c:c.execute(text('DROP DATABASE IF EXISTS "'+self.name+'" WITH (FORCE)'))
        self.admin.dispose()

    def initialize(self,failpoint=None,marker=None):
        environment={**os.environ,'DATABASE_URL':self.target.render_as_string(hide_password=False)}
        if failpoint:environment['PVNETWORK_SCHEMA_FAILPOINT']=failpoint
        args=[sys.executable,ROOT/'scripts/pvnetwork_initialize_database.py','--project',ROOT]
        if marker:args.extend(['--completion-marker',marker])
        return subprocess.run(args,env=environment,capture_output=True,text=True)

    def test_current_schema_head_and_database_constraints(self):
        result=self.initialize();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        tables=inspect(self.engine).get_table_names()
        self.assertIn('active_sessions',tables);self.assertIn('users',tables);self.assertIn('nodes',tables)
        with self.engine.connect() as c:self.assertEqual(c.execute(text('SELECT version_num FROM alembic_version')).scalar_one(),'i1b2c3d4e5f6')
        constraints=inspect(self.engine).get_check_constraints('users')
        self.assertTrue(any('device_limit' in c['sqltext'] for c in constraints))
        again=self.initialize();self.assertNotEqual(again.returncode,0);self.assertIn('existing database schema refused',again.stderr)

    def test_failed_creation_rolls_back_every_table_and_head(self):
        result=self.initialize('after_create');self.assertNotEqual(result.returncode,0)
        self.assertIn('requested disposable schema fault injection',result.stderr)
        self.assertEqual(inspect(self.engine).get_table_names(),[])

    def test_additive_legacy_head_upgrade_preserves_customer_data_and_attestations(self):
        import importlib.util
        result=self.initialize();self.assertEqual(result.returncode,0,result.stderr)
        with self.engine.begin() as c:
            c.execute(text("UPDATE alembic_version SET version_num='h0a1b2c3d4e5'"))
            c.execute(text("INSERT INTO users(uuid,name,total,used,last_node_usage,expiry_date,is_active,owner,device_limit) VALUES ('demo-migration-uuid','demo-migration',1234567,7654,0,'2030-01-01',true,'demo-owner',1)"))
            c.execute(text("INSERT INTO node_tls_bindings VALUES (:identity,'192.0.2.10',9443,:ca,:credential)"),{'identity':'a'*64,'ca':'b'*64,'credential':'c'*64})
        spec=importlib.util.spec_from_file_location('pg_binding_lifecycle',ROOT/'scripts/pvnetwork_lifecycle.py')
        lifecycle=importlib.util.module_from_spec(spec);spec.loader.exec_module(lifecycle)
        environment={'DATABASE_URL':self.target.render_as_string(hide_password=False)}
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder);(stage/'backend').symlink_to(ROOT/'backend',target_is_directory=True)
            (stage/'.venv').symlink_to(Path(sys.prefix),target_is_directory=True)
            lifecycle.STATE=stage/'private-state'
            before=lifecycle.database_fingerprint(environment)
            plan=lifecycle.migration_plan(stage,environment)
            lifecycle.migrate_additive(stage,environment,plan)
            for table,signature in before.items():
                if table!='alembic_version':self.assertEqual(lifecycle.database_fingerprint(environment)[table],signature)
            lifecycle.migrate_additive(stage,environment,plan)
            self.assertEqual(lifecycle._db_head(environment),'i1b2c3d4e5f6')
            # The other supported predecessor has no runtime-created binding
            # table. This is a dedicated disposable database, never Production.
            with self.engine.begin() as c:
                c.execute(text('DELETE FROM node_tls_bindings'))
                c.execute(text('DROP TABLE node_tls_bindings'))
                c.execute(text("UPDATE alembic_version SET version_num='h0a1b2c3d4e5'"))
            before=lifecycle.database_fingerprint(environment)
            lifecycle.migrate_additive(stage,environment,plan)
            after=lifecycle.database_fingerprint(environment)
            self.assertEqual(set(after)-set(before),{'node_tls_bindings'})
            for table,signature in before.items():
                if table!='alembic_version':self.assertEqual(after[table],signature)

    def test_owned_commit_before_journal_is_recoverable_but_data_is_never_reinitialized(self):
        with tempfile.TemporaryDirectory() as folder:
            marker=str(Path(folder)/'ownership.json')
            result=self.initialize('after_commit',marker);self.assertNotEqual(result.returncode,0)
            self.assertIn('interruption after database commit',result.stderr)
            recovered=self.initialize(marker=marker);self.assertEqual(recovered.returncode,0,recovered.stderr)
            self.assertIn('OWNED_FRESH_DATABASE_ALREADY_INITIALIZED',recovered.stdout)
            with self.engine.begin() as c:
                c.execute(text("INSERT INTO users(uuid,name,total,used,last_node_usage,expiry_date,is_active,owner,device_limit) VALUES ('demo-preserved-uuid','demo-preserved',1234567,0,0,'2030-01-01',true,'demo-owner',1)"))
            refused=self.initialize(marker=marker);self.assertNotEqual(refused.returncode,0)
            with self.engine.connect() as c:self.assertEqual(c.execute(text('SELECT uuid FROM users')).scalar_one(),'demo-preserved-uuid')
