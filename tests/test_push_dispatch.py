import hashlib
import os
import threading
import tempfile
import time
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault('ADMIN_USERNAME', 'ci-admin')
os.environ.setdefault('ADMIN_PASSWORD_HASH', '$2b$12$abcdefghijklmnopqrstuu1234567890123456789012')
os.environ.setdefault('JWT_SECRET_KEY', 'ci-private-demo-jwt-secret-over-32-characters')

from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pywebpush import WebPushException
from backend.db.engine import Base, get_db
from backend.db.models import User
from backend.routers import push
from tests.test_node_archive_api import AsgiClient


class PushDispatchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(User(uuid='demo-user', name='alice', owner='seller', total=1000, used=600,
            expiry_date=date(2030,1,1), is_active=True, device_limit=1))
        self.db.commit()
        push.ensure_push_table(self.db)
        self.endpoint='https://fcm.googleapis.com/fcm/send/demo'
        self.add_subscription(self.endpoint)
        self.app=FastAPI()
        self.app.include_router(push.router)
        def dependency(): yield self.db
        self.app.dependency_overrides[get_db]=dependency
        self.client=AsgiClient(self.app)
        self.root=push.router.prefix

    def add_subscription(self, endpoint):
        self.db.execute(text('INSERT INTO web_push_subscriptions (endpoint_hash,user_uuid,endpoint,p256dh,auth,enabled,created_at,updated_at) VALUES (:hash,:uuid,:url,:key,:auth,1,1,1)'),
            {'hash':hashlib.sha256(endpoint.encode()).hexdigest(), 'uuid':'demo-user', 'url':endpoint, 'key':'demo-key', 'auth':'demo-auth'})
        self.db.commit()

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def request(self, endpoint=None):
        return self.client.post(self.root+'/test/demo-user',json={'endpoint':endpoint or self.endpoint})

    def test_exactly_one_test_route(self):
        routes=[r for r in push.router.routes if r.path.endswith('/test/{uuid}') and 'POST' in r.methods]
        self.assertEqual(len(routes),1)

    def test_success_then_repeat_and_new_subscription_cannot_bypass_budget(self):
        with patch.object(push,'webpush',return_value=SimpleNamespace(status_code=201)) as send:
            first=self.request()
            self.assertEqual(first.status_code,200)
            self.assertEqual(self.request().status_code,429)
            other='https://fcm.googleapis.com/fcm/send/another-demo'
            self.add_subscription(other)
            self.assertEqual(self.request(other).status_code,429)
        send.assert_called_once()

    def test_provider_failure_still_reserves_budget_and_error_is_private(self):
        error=WebPushException('private provider endpoint and payload')
        with patch.object(push,'webpush',side_effect=error) as send:
            first=self.request()
            self.assertEqual(first.status_code,502)
            self.assertNotIn('private provider',first.text)
            self.assertEqual(self.request().status_code,429)
        send.assert_called_once()

    def test_delivery_runs_off_event_loop(self):
        threads=[]
        def deliver(**_kwargs):
            threads.append(threading.get_ident())
            return SimpleNamespace(status_code=201)
        with patch.object(push,'webpush',side_effect=deliver):
            self.assertEqual(self.request().status_code,200)
        self.assertNotEqual(threads,[threading.get_ident()])

    def test_old_schema_without_last_test_column_works_and_budget_is_persisted(self):
        columns=[row[1] for row in self.db.execute(text('PRAGMA table_info(web_push_subscriptions)'))]
        self.assertNotIn('last_test_at',columns)
        with patch.object(push,'webpush',return_value=SimpleNamespace(status_code=201)):
            self.assertEqual(self.request().status_code,200)
        self.db.close(); self.db=self.Session()
        self.assertEqual(self.request().status_code,429)

    def test_expired_budget_allows_legitimate_next_test(self):
        with patch.object(push,'webpush',return_value=SimpleNamespace(status_code=201)) as send:
            self.assertEqual(self.request().status_code,200)
            self.db.execute(text('UPDATE web_push_test_budget SET last_test_at=:old'),{'old':int(time.time())-3601})
            self.db.commit()
            self.assertEqual(self.request().status_code,200)
        self.assertEqual(send.call_count,2)

    def test_capacity_is_bounded_before_outbound_work(self):
        acquired=[]
        try:
            for _ in range(4):
                self.assertTrue(push._TEST_DELIVERIES.acquire(blocking=False))
                acquired.append(True)
            with patch.object(push,'webpush') as send:
                response=self.request()
            self.assertEqual(response.status_code,503)
            send.assert_not_called()
        finally:
            for _ in acquired: push._TEST_DELIVERIES.release()

    def test_independent_database_sessions_race_for_one_persisted_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=create_engine('sqlite:///'+directory+'/budget.db',connect_args={'check_same_thread':False})
            Base.metadata.create_all(engine)
            Session=sessionmaker(bind=engine)
            with Session() as db:
                db.add(User(uuid='demo-user', name='alice', owner='seller', total=1000, used=600,
                    expiry_date=date(2030,1,1), is_active=True, device_limit=1))
                db.commit()
                push.ensure_push_table(db)
                db.execute(text('INSERT INTO web_push_subscriptions (endpoint_hash,user_uuid,endpoint,p256dh,auth,enabled,created_at,updated_at) VALUES (:hash,:uuid,:url,:key,:auth,1,1,1)'),
                    {'hash':'demo-hash','uuid':'demo-user','url':self.endpoint,'key':'demo-key','auth':'demo-auth'})
                db.commit()
            app=FastAPI();app.include_router(push.router)
            def dependency():
                with Session() as db: yield db
            app.dependency_overrides[get_db]=dependency
            barrier=threading.Barrier(2)
            def run():
                barrier.wait(timeout=5)
                return AsgiClient(app).post(self.root+'/test/demo-user',json={'endpoint':self.endpoint}).status_code
            with patch.object(push,'webpush',return_value=SimpleNamespace(status_code=201)) as send, ThreadPoolExecutor(max_workers=2) as executor:
                results=list(executor.map(lambda _:run(),range(2)))
            self.assertEqual(sorted(results),[200,429])
            send.assert_called_once()
            engine.dispose()
