"""Exercise collector ingestion against real SQL, including existing SQLite DDL."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

os.environ.setdefault('JWT_SECRET_KEY', 'demo-domain-test-secret-not-production-32chars')
os.environ.setdefault('ADMIN_USERNAME', 'demo-admin')
os.environ.setdefault('ADMIN_PASSWORD_HASH', 'demo-test-only-hash')

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from backend.db.models import DomainActivity, Node, User, UserNode
from backend.routers import domain_activity as domain


def seed(engine):
    with sessionmaker(bind=engine)() as db:
        db.add_all([
            Node(id=1, name='demo-node', address='192.0.2.1', protocol='udp',
                 ovpn_port=1194, port=9443, key='demo-domain-node-key', status=True),
            Node(id=2, name='other-node', address='192.0.2.2', protocol='udp',
                 ovpn_port=1194, port=9443, key='demo-other-node-key', status=True),
            User(uuid='demo-domain-user', name='demo-user', owner='demo-owner',
                 total=1000, used=0, expiry_date=date(2030, 1, 1), device_limit=1),
        ])
        db.commit()
        db.add(UserNode(user_uuid='demo-domain-user', node_id=1))
        db.commit()


def event(domain_name='a.example.com', *, first=None, last=None, hits=1, cn='demo-user-demo-node'):
    now=int(time.time())
    return domain.DomainActivityEvent(common_name=cn, domain=domain_name,
        first_seen=now-10 if first is None else first,
        last_seen=now if last is None else last, hit_count=hits)


def ingest(engine, events, key='demo-domain-node-key'):
    with sessionmaker(bind=engine)() as db:
        return asyncio.run(domain.ingest_domain_activity(
            domain.DomainActivityBatch(events=events), db=db, node_key=key))


def assert_merge(case, engine):
    now=int(time.time())
    first=ingest(engine, [event(first=now-20, last=now-10, hits=2),
                          event('b.example.com', first=now-15, last=now-5, hits=3)])
    case.assertEqual((first['accepted_domains'], first['accepted_hits']), (1, 5))
    ingest(engine, [event(first=now-40, last=now, hits=7), event('demo.example.net')])
    with sessionmaker(bind=engine)() as db:
        rows=db.query(DomainActivity).order_by(DomainActivity.domain).all()
        case.assertEqual(len(rows), 2)
        case.assertEqual(len({row.id for row in rows}), 2)
        case.assertEqual((rows[0].domain, rows[0].first_seen, rows[0].last_seen,
                          rows[0].hit_count), ('example.com', now-40, now, 12))
        case.assertTrue(all(row.id is not None for row in rows))


class DomainActivityIngestTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.engine=create_engine('sqlite:///'+str(Path(self.folder.name)/'domain.db'),
                                  connect_args={'timeout':15})
        for table in [Node.__table__, User.__table__, UserNode.__table__, DomainActivity.__table__]:
            table.create(self.engine)
        seed(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.folder.cleanup()

    def test_new_and_repeated_batches_preserve_range_and_add_hits(self):
        assert_merge(self, self.engine)

    def test_node_key_assignment_and_domain_privacy_guards(self):
        with self.assertRaises(HTTPException) as failure:
            ingest(self.engine, [event()], 'unknown-demo-key')
        self.assertEqual(failure.exception.status_code, 401)
        result=ingest(self.engine, [event(cn='demo-user-other-node')], 'demo-other-node-key')
        self.assertEqual((result['accepted_domains'], result['ignored']), (0, 1))
        result=ingest(self.engine, [event('127.0.0.1'), event('host.local'), event('https://example.com/path')])
        self.assertEqual((result['accepted_domains'], result['ignored']), (0, 3))

    def test_concurrent_batches_do_not_lose_hits_or_collide_ids(self):
        for mode in ['delete', 'wal']:
            with self.subTest(journal=mode):
                with self.engine.begin() as connection:
                    connection.execute(text('DELETE FROM domain_activity'))
                with self.engine.connect() as connection:
                    connection.execute(text('PRAGMA journal_mode='+mode))
                barrier=threading.Barrier(2)
                def deliver(index):
                    barrier.wait(timeout=5)
                    return ingest(self.engine, [event(hits=3), event(f'item-{index}.example.org')])
                with ThreadPoolExecutor(max_workers=2) as pool:
                    list(pool.map(deliver, range(2)))
                with sessionmaker(bind=self.engine)() as db:
                    rows=db.query(DomainActivity).all()
                    self.assertEqual(len(rows), 2)
                    self.assertEqual(len({row.id for row in rows}), 2)
                    self.assertEqual(next(row.hit_count for row in rows if row.domain=='example.com'), 6)

    def test_maximum_batch_has_unique_ids_and_reads_back_in_admin_history(self):
        result=ingest(self.engine, [event(f'demo-{index}.invalid') for index in range(1000)])
        self.assertEqual(result['accepted_domains'], 1000)
        with sessionmaker(bind=self.engine)() as db:
            rows=db.query(DomainActivity).all()
            self.assertEqual(len({row.id for row in rows}), 1000)
            response=asyncio.run(domain.get_user_domain_activity('demo-domain-user',
                search='', days=7, page=1, page_size=25, db=db, actor={'type':'main_admin'}))
            self.assertEqual(response.data['total'], 1000)
            self.assertEqual(len(response.data['items']), 25)

    def test_failed_batch_rolls_back_all_domain_changes(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER fail_demo_domain BEFORE INSERT ON domain_activity "
                "WHEN NEW.domain = 'example.net' BEGIN SELECT RAISE(ABORT, 'demo batch rejected'); END"))
        with self.assertRaises(IntegrityError):
            ingest(self.engine, [event('example.com'), event('example.net')])
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.query(DomainActivity).count(), 0)
        ingest(self.engine, [event('example.com')])
        with sessionmaker(bind=self.engine)() as db:
            self.assertEqual(db.query(DomainActivity).one().hit_count, 1)
