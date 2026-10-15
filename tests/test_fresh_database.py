"""Real fresh schema construction and refusal to touch an existing database."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class FreshDatabaseTests(unittest.TestCase):
    def initialize(self, db, *, failpoint=None):
        env={**os.environ,'DATABASE_URL':'sqlite:///'+str(db)}
        if failpoint:env['PVNETWORK_SCHEMA_FAILPOINT']=failpoint
        return subprocess.run([sys.executable,str(ROOT/'scripts/pvnetwork_initialize_database.py'),'--project',str(ROOT)],env=env,capture_output=True,text=True,timeout=30)

    def test_current_empty_sqlite_has_head_constraints_and_session_key(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'fresh.db';result=self.initialize(db)
            self.assertEqual(result.returncode,0,result.stderr)
            with sqlite3.connect(db) as connection:
                head=connection.execute('SELECT version_num FROM alembic_version').fetchone()[0]
                self.assertEqual(head,'i1b2c3d4e5f6')
                schema=connection.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
                self.assertIn('ck_users_device_limit_nonnegative',schema)
                info=connection.execute('PRAGMA table_info(active_sessions)').fetchall()
                self.assertTrue(any(row[1]=='session_id' and row[5] for row in info))
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)

    def test_schema_failure_leaves_original_empty_database_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'fresh.db'
            with sqlite3.connect(db):pass
            before=db.read_bytes();r=self.initialize(db,failpoint='after_create')
            self.assertNotEqual(r.returncode,0)
            self.assertIn('requested disposable schema fault injection',r.stderr)
            self.assertEqual(db.read_bytes(),before)
            self.assertFalse(list(Path(folder).glob('*.initialize-*')))

    def test_existing_data_and_schema_are_never_reinitialized(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'existing.db'
            with sqlite3.connect(db) as c:
                c.execute('CREATE TABLE sentinel(value TEXT)');c.execute("INSERT INTO sentinel VALUES ('preserved')")
            before=db.read_bytes();result=self.initialize(db)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('existing database schema refused',result.stderr)
            self.assertEqual(db.read_bytes(),before)
            with sqlite3.connect(db) as c:self.assertEqual(c.execute('SELECT value FROM sentinel').fetchone()[0],'preserved')

    def test_negative_device_limit_is_rejected_by_database(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'fresh.db';r=self.initialize(db);self.assertEqual(r.returncode,0,r.stderr)
            with sqlite3.connect(db) as c:
                with self.assertRaises(sqlite3.IntegrityError):
                    c.execute("INSERT INTO users (uuid,name,expiry_date,is_active,owner,device_limit) VALUES ('demo-id','demo-user','2030-01-01',1,'demo-admin',-1)")
