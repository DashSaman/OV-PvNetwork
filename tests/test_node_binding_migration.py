"""Real additive SQLite migration preserves data and attested TLS bindings."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import sys
import os
import signal
import subprocess
import time

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]


class NodeBindingMigrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.folder.name) / 'data.db'))
        spec = importlib.util.spec_from_file_location('binding_migration', ROOT / 'backend/alembic/versions/i1b2c3d4e5f6_native_node_tls_binding.py')
        self.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.migration)
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE users(uuid TEXT PRIMARY KEY,used BIGINT)'))
            connection.execute(text("INSERT INTO users VALUES ('preserved-demo-uuid',987654321)"))

    def tearDown(self):
        self.engine.dispose()
        self.folder.cleanup()

    def migrate(self, action):
        with self.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                getattr(self.migration, action)()

    def test_upgrade_creates_only_binding_and_keeps_customer_rows(self):
        self.migrate('upgrade')
        self.assertEqual(set(inspect(self.engine).get_table_names()), {'users', 'node_tls_bindings'})
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT * FROM users')).one(), ('preserved-demo-uuid',987654321))
        self.migrate('downgrade')
        self.assertEqual(inspect(self.engine).get_table_names(), ['users'])

    def test_existing_attested_binding_is_preserved_and_downgrade_refused(self):
        self.migrate('upgrade')
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO node_tls_bindings VALUES (:identity,'192.0.2.10',9443,:ca,:credential)"), {'identity':'a'*64,'ca':'b'*64,'credential':'c'*64})
        self.migrate('upgrade')
        with self.assertRaisesRegex(ValueError, 'attested node'):
            self.migrate('downgrade')
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT credential_sha256 FROM node_tls_bindings')).scalar_one(), 'c'*64)

    def test_foreign_table_definition_is_refused_without_changing_it(self):
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE node_tls_bindings(identity TEXT,credential TEXT)'))
            connection.execute(text("INSERT INTO node_tls_bindings VALUES ('foreign','preserved')"))
        with self.assertRaisesRegex(ValueError, 'schema'):
            self.migrate('upgrade')
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT * FROM node_tls_bindings')).one(), ('foreign','preserved'))

    def test_real_lifecycle_migration_and_replay_preserve_every_original_row(self):
        spec=importlib.util.spec_from_file_location('binding_lifecycle',ROOT/'scripts/pvnetwork_lifecycle.py')
        lifecycle=importlib.util.module_from_spec(spec);spec.loader.exec_module(lifecycle)
        root=Path(self.folder.name);stage=root/'candidate';stage.mkdir()
        (stage/'backend').symlink_to(ROOT/'backend',target_is_directory=True)
        (stage/'.venv').symlink_to(Path(sys.prefix),target_is_directory=True)
        lifecycle.STATE=root/'private-state'
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE alembic_version(version_num VARCHAR(32) PRIMARY KEY)'))
            connection.execute(text("INSERT INTO alembic_version VALUES ('h0a1b2c3d4e5')"))
        environment={'DATABASE_URL':str(self.engine.url)}
        before=lifecycle.database_fingerprint(environment)
        plan=lifecycle.migration_plan(stage,environment)
        lifecycle.migrate_additive(stage,environment,plan)
        self.assertEqual(lifecycle.database_fingerprint(environment)['users'],before['users'])
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO node_tls_bindings VALUES (:identity,'192.0.2.10',9443,:ca,:credential)"),{'identity':'a'*64,'ca':'b'*64,'credential':'c'*64})
        attested=lifecycle.database_fingerprint(environment)
        lifecycle.migrate_additive(stage,environment,plan)
        self.assertEqual(lifecycle.database_fingerprint(environment),attested)
        self.assertTrue(lifecycle.schema_compatible_with_previous('h0a1b2c3d4e5',lifecycle._db_head(environment)))

    @unittest.skipUnless(os.name=='posix','SIGKILL requires isolated Linux QA')
    def test_actual_sigkill_after_schema_commit_replays_without_losing_rows(self):
        root=Path(self.folder.name);stage=root/'candidate';stage.mkdir()
        (stage/'backend').symlink_to(ROOT/'backend',target_is_directory=True)
        (stage/'.venv').symlink_to(Path(sys.prefix),target_is_directory=True)
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE alembic_version(version_num VARCHAR(32) PRIMARY KEY)'))
            connection.execute(text("INSERT INTO alembic_version VALUES ('h0a1b2c3d4e5')"))
        marker=root/'committed';program=root/'migrate_child.py'
        program.write_text("import os,signal,sys\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nimport pvnetwork_lifecycle as m\nm.STATE=Path(sys.argv[2]).parent/'private-state'\nenv={'DATABASE_URL':sys.argv[3]}\np=m.migration_plan(sys.argv[2],env)\nm.migrate_additive(sys.argv[2],env,p)\nPath(sys.argv[4]).write_text('committed')\nos.kill(os.getpid(),signal.SIGSTOP)\n")
        child=subprocess.Popen([sys.executable,program,str(ROOT/'scripts'),str(stage),str(self.engine.url),str(marker)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+30
            while not marker.exists():
                if child.poll() is not None:self.fail(child.stderr.read().decode())
                if time.monotonic()>deadline:self.fail('migration commit checkpoint not reached')
                time.sleep(.05)
            os.kill(child.pid,signal.SIGKILL);child.wait(timeout=10)
            self.assertEqual(child.returncode,-signal.SIGKILL)
            spec=importlib.util.spec_from_file_location('killed_binding_lifecycle',ROOT/'scripts/pvnetwork_lifecycle.py')
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            m.STATE=root/'private-state'
            env={'DATABASE_URL':str(self.engine.url)};before=m.database_fingerprint(env)
            plan={'from':'h0a1b2c3d4e5','to':'i1b2c3d4e5f6','script_sha256':m.sha256(stage/'backend/alembic/versions/i1b2c3d4e5f6_native_node_tls_binding.py')}
            m.migrate_additive(stage,env,plan)
            self.assertEqual(m.database_fingerprint(env),before)
            self.assertEqual(before['users']['count'],1)
        finally:
            if child.poll() is None:child.kill();child.wait()
            child.stderr.close()
