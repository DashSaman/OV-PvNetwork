"""Exercise the actual subscription route against the locked template API."""
import os
import unittest
from datetime import date
from html.parser import HTMLParser
from unittest.mock import patch

os.environ.setdefault('ADMIN_USERNAME', 'ci-admin')
os.environ.setdefault('ADMIN_PASSWORD_HASH', '$2b$12$abcdefghijklmnopqrstuu1234567890123456789012')
os.environ.setdefault('JWT_SECRET_KEY', 'ci-subscription-contract-secret-over-32-characters')

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.db.engine import Base, get_db
from backend.db.models import User, Node, UserNode
from backend.routers import sub
from tests.test_node_archive_api import AsgiClient


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.extend(value for key, value in attrs if key == 'href')


class SubscriptionRouteContractTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add(User(uuid='synthetic-sub-user', name='<img src=x onerror=alert(1)>', owner='demo-owner',
                total=10000, used=100, expiry_date=date(2030, 1, 1), is_active=True, device_limit=2))
            db.commit()
        app = FastAPI()
        app.include_router(sub.router)
        def database():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = database
        self.client = AsgiClient(app)
        self.path = sub.router.prefix + '/synthetic-sub-user'

    def tearDown(self):
        self.engine.dispose()

    def add_node(self, *, assigned=True, **values):
        with self.Session() as db:
            node = Node(name='DemoNode', address='node.example.invalid', port=9443, key='synthetic-node-api-secret',
                protocol='udp', ovpn_port=1194, status=True)
            for key, value in values.items():
                setattr(node, key, value)
            db.add(node)
            db.flush()
            if assigned:
                db.add(UserNode(user_uuid='synthetic-sub-user', node_id=node.id))
            db.commit()
            return node.id

    def assert_rendered(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', response.text)
        self.assertNotIn('<img src=x onerror=alert(1)>', response.text)
        self.assertNotIn('synthetic-node-api-secret', response.text)
        links = Links()
        links.feed(response.text)
        return links.hrefs

    def test_assigned_healthy_node_renders_with_real_template_and_escaped_user(self):
        self.add_node()
        info = {'status': 'running', 'rx_bytes': 1000, 'tx_bytes': 2000}
        with patch.object(sub.NodeRequests, 'get_node_info', return_value=info):
            links = self.assert_rendered(self.client.get(self.path))
        self.assertIn('https://test.invalid' + sub.router.prefix + '/download/synthetic-sub-user/DemoNode', links)

    def test_no_nodes_renders_without_network(self):
        with patch.object(sub, 'NodeRequests', side_effect=AssertionError('Unexpected node probe')):
            links = self.assert_rendered(self.client.get(self.path))
        self.assertFalse(any('/download/synthetic-sub-user/' in x for x in links))

    def test_unavailable_assigned_node_renders_without_download(self):
        self.add_node()
        with patch.object(sub.NodeRequests, 'get_node_info', side_effect=TimeoutError('Synthetic unavailable node')):
            links = self.assert_rendered(self.client.get(self.path))
        self.assertFalse(any('/download/synthetic-sub-user/' in x for x in links))

    def test_disabled_draining_and_maintenance_nodes_are_not_probed(self):
        for values in [{'status': False}, {'drain': True}, {'maintenance': True}]:
            with self.subTest(values=values):
                node_id = self.add_node(**values)
                with patch.object(sub, 'NodeRequests', side_effect=AssertionError('Unexpected node probe')):
                    links = self.assert_rendered(self.client.get(self.path))
                self.assertFalse(any('/download/synthetic-sub-user/' in x for x in links))
                with self.Session() as db:
                    db.query(UserNode).delete()
                    db.query(Node).filter(Node.id == node_id).delete()
                    db.commit()

    def test_missing_user_is_404_before_node_probe(self):
        with patch.object(sub, 'NodeRequests', side_effect=AssertionError('Unexpected node probe')):
            self.assertEqual(self.client.get(sub.router.prefix + '/missing-synthetic-user').status_code, 404)

    def test_unassigned_node_download_remains_404(self):
        self.add_node()
        self.add_node(name='Unassigned', assigned=False)
        with patch.object(sub, 'download_ovpn_client_from_node', side_effect=AssertionError('Unexpected profile fetch')):
            response = self.client.get(sub.router.prefix + '/download/synthetic-sub-user/Unassigned')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('synthetic-node-api-secret', response.text)
