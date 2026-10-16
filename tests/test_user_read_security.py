import asyncio
import hashlib
import json
import os
import time
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

os.environ.setdefault('ADMIN_USERNAME', 'ci-admin')
os.environ.setdefault('ADMIN_PASSWORD', 'ci-private-demo-password')
os.environ.setdefault('JWT_SECRET_KEY', 'ci-private-demo-jwt-secret-over-32-characters')

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth.auth import get_current_user
from backend.db.engine import Base, get_db
from backend.db.models import ApiToken, User
from backend.routers import users
from backend.routers import setting
from backend.security_middleware import ApiScopeMiddleware


class UserReadSecurityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.db.add_all([
            User(uuid='own-demo', name='alice', owner='seller', total=1000, used=600,
                 last_node_usage=500, expiry_date=date(2030, 1, 1), is_active=True, device_limit=1),
            User(uuid='other-demo', name='bob', owner='other', total=1000, used=400,
                 expiry_date=date(2030, 1, 1), is_active=True, device_limit=1),
        ])
        self.actor = {'type': 'main_admin', 'username': 'owner', 'auth_kind': 'api_token'}
        self.read_token = self.token('read', ['users:read'])
        self.write_token = self.token('write', ['users:write'])
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(users.router, prefix='/api')
        self.app.include_router(setting.router, prefix='/api')
        self.app.add_middleware(ApiScopeMiddleware)
        def db_dependency():
            yield self.db
        self.app.dependency_overrides[get_db] = db_dependency
        self.app.dependency_overrides[get_current_user] = lambda: self.actor
        self.presence = {'counts_by_uuid': {'own-demo': 1, 'other-demo': 2}, 'sample_time': 123}
        self.rates = {'rates_bps_by_uuid': {'own-demo': {'rx': 4}, 'other-demo': {'rx': 9}}}
        self.patches = [
            patch('backend.security_middleware.SessionLocal', self.Session),
            patch.object(users, 'get_display_live_presence', AsyncMock(return_value=self.presence)),
            patch.object(users, 'get_user_live_rates', AsyncMock(return_value=self.rates)),
            patch.object(users, 'reset_shared_user_usage', AsyncMock(side_effect=self.reset)),
            patch('backend.db.engine.sessionLocal', self.Session),
        ]
        for item in self.patches: item.start()

    def token(self, label, scopes):
        raw = 'pvn_demo-security-' + label
        self.db.add(ApiToken(id=1 if label == 'read' else 2, name=label, token_prefix=raw[:12],
            token_hash=hashlib.sha256(raw.encode()).hexdigest(), scopes=json.dumps(scopes),
            created_at=int(time.time()), created_by='owner'))
        return raw

    async def reset(self, target, db):
        target.used = 0
        target.last_node_usage = 0
        db.commit()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.db.close()
        self.engine.dispose()

    async def request(self, method, path, token=None):
        path = '/api' + path
        headers = [(b'authorization', ('Bearer ' + token).encode())] if token else []
        messages = []
        read = False
        async def receive():
            nonlocal read
            if not read:
                read = True
                return {'type': 'http.request', 'body': b'', 'more_body': False}
            await asyncio.Event().wait()
        async def send(message): messages.append(message)
        await self.app({'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
            'http_version': '1.1', 'scheme': 'http', 'method': method, 'path': path,
            'raw_path': path.encode(), 'query_string': b'', 'root_path': '',
            'server': ('test.invalid', 80), 'client': ('127.0.0.1', 1234),
            'headers': headers}, receive, send)
        status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
        body = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
        return SimpleNamespace(status_code=status, json=lambda: json.loads(body))

    def snapshot(self):
        self.db.expire_all()
        row = self.db.query(User).filter_by(uuid='own-demo').one()
        return (row.used, row.last_node_usage, row.expiry_date, row.is_active)

    async def test_reseller_presence_contains_only_owned_uuid_in_every_map(self):
        self.actor = {'type': 'admin', 'username': 'seller'}
        response = await self.request('GET', '/users/presence')
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertNotIn('other-demo', json.dumps(data))
        self.assertEqual(data['counts_by_uuid'], {'own-demo': 1})
        self.assertEqual(data['rates_bps_by_uuid'], {'own-demo': {'rx': 4}})
        self.assertEqual(self.rates['rates_bps_by_uuid']['other-demo'], {'rx': 9})

    async def test_main_admin_keeps_global_presence(self):
        response = await self.request('GET', '/users/presence', self.read_token)
        self.assertEqual(set(response.json()['data']['rates_bps_by_uuid']), {'own-demo', 'other-demo'})

    async def test_dashboard_cache_never_leaks_other_tenant_uuid_and_stays_global_for_admin(self):
        cached={'nodes':[], 'presence':self.presence, 'sample_time':123}
        with patch.dict(setting._dashboard_live_cache, {'time':time.monotonic(), 'data':cached}, clear=True):
            self.actor={'type':'admin', 'username':'seller'}
            response=await self.request('GET','/server/dashboard-live')
            self.assertEqual(response.status_code,200)
            self.assertNotIn('other-demo',json.dumps(response.json()))
            self.assertEqual(response.json()['data']['presence']['counts_by_uuid'], {'own-demo':1})
            self.assertIn('other-demo',cached['presence']['counts_by_uuid'])
            self.actor={'type':'main_admin','username':'owner'}
            response=await self.request('GET','/server/dashboard-live')
            self.assertIn('other-demo',response.json()['data']['presence']['counts_by_uuid'])

    async def test_uncached_dashboard_filters_before_serialization(self):
        self.actor={'type':'admin','username':'seller'}
        with patch.dict(setting._dashboard_live_cache,{},clear=True), patch('backend.operations.live_presence.get_display_live_presence',AsyncMock(return_value=self.presence)):
            response=await self.request('GET','/server/dashboard-live')
        self.assertEqual(response.status_code,200)
        self.assertNotIn('other-demo',json.dumps(response.json()))

    async def test_get_detail_is_read_only_and_owner_scoped(self):
        before = self.snapshot()
        response = await self.request('GET', '/users/own-demo', self.read_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.snapshot(), before)
        users.reset_shared_user_usage.assert_not_awaited()
        self.assertEqual(response.json()['data']['uuid'], 'own-demo')
        self.actor = {'type': 'admin', 'username': 'seller'}
        hidden = await self.request('GET', '/users/other-demo')
        self.assertEqual(hidden.status_code, 404)

    async def test_cli_session_route_cannot_reset_usage(self):
        before=self.snapshot()
        response=await self.request('GET','/users/own-demo/sessions',self.read_token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['data']['online_count'],1)
        self.assertEqual(self.snapshot(),before)
        users.reset_shared_user_usage.assert_not_awaited()

    async def test_reset_requires_write_and_preserves_existing_reset_behavior(self):
        before = self.snapshot()
        denied = await self.request('POST', '/users/own-demo/reset', self.read_token)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.snapshot(), before)
        users.reset_shared_user_usage.assert_not_awaited()
        allowed = await self.request('POST', '/users/own-demo/reset', self.write_token)
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()['success'])
        self.assertEqual(self.snapshot(), (0, 0, before[2], before[3]))
        users.reset_shared_user_usage.assert_awaited_once()

    async def test_unlimited_reset_still_renews_and_cross_tenant_reset_is_hidden(self):
        row = self.db.query(User).filter_by(uuid='own-demo').one()
        row.total = 0
        row.is_active = False
        self.db.commit()
        with patch.object(users, 'change_user_status_on_assigned_nodes', AsyncMock(return_value={'ok':True})) as sync:
            allowed = await self.request('POST', '/users/own-demo/reset', self.write_token)
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()['data']['renewed'])
        self.assertEqual(self.snapshot()[2:], (date.today()+timedelta(days=30), True))
        sync.assert_awaited_once()
        self.actor = {'type':'admin', 'username':'seller'}
        hidden = await self.request('POST', '/users/other-demo/reset')
        self.assertEqual(hidden.status_code, 404)


if __name__ == '__main__':
    unittest.main()
