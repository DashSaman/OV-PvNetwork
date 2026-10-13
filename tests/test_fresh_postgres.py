"""Real empty PostgreSQL initialization; only a dedicated loopback QA service."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
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

    def initialize(self,failpoint=None):
        environment={**os.environ,'DATABASE_URL':self.target.render_as_string(hide_password=False)}
        if failpoint:environment['PVNETWORK_SCHEMA_FAILPOINT']=failpoint
        return subprocess.run([sys.executable,ROOT/'scripts/pvnetwork_initialize_database.py','--project',ROOT],env=environment,capture_output=True,text=True)

    def test_current_schema_head_and_database_constraints(self):
        result=self.initialize();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        tables=inspect(self.engine).get_table_names()
        self.assertIn('active_sessions',tables);self.assertIn('users',tables);self.assertIn('nodes',tables)
        with self.engine.connect() as c:self.assertEqual(c.execute(text('SELECT version_num FROM alembic_version')).scalar_one(),'h0a1b2c3d4e5')
        constraints=inspect(self.engine).get_check_constraints('users')
        self.assertTrue(any('device_limit' in c['sqltext'] for c in constraints))
        again=self.initialize();self.assertNotEqual(again.returncode,0);self.assertIn('existing database schema refused',again.stderr)

    def test_failed_creation_rolls_back_every_table_and_head(self):
        result=self.initialize('after_create');self.assertNotEqual(result.returncode,0)
        self.assertIn('requested disposable schema fault injection',result.stderr)
        self.assertEqual(inspect(self.engine).get_table_names(),[])
