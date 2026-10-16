"""The downloaded client must use one current endpoint without changing identity."""
from datetime import date
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('ADMIN_USERNAME', 'demo-admin')
os.environ.setdefault('ADMIN_PASSWORD_HASH', 'demo-test-only-hash')
os.environ.setdefault('JWT_SECRET_KEY', 'demo-profile-test-not-production-secret-32chars')

from fastapi.responses import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.models import Node, User
from backend.node import task


class ProfileDownloadEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        Node.__table__.create(self.engine);User.__table__.create(self.engine)
        self.db=sessionmaker(bind=self.engine)()
        self.db.add_all([
            Node(id=1, name='demo-node', address='node.example.invalid',
                 tunnel_address='vpn.example.invalid', protocol='tcp', ovpn_port=443,
                 port=9443, key='demo-profile-node-key', status=True),
            User(uuid='demo-profile-user', name='demo-user', owner='demo-owner',
                 total=1000, used=0, expiry_date=date(2030,1,1), device_limit=1),
        ])
        self.db.commit()
        self.identity=''.join('<'+tag+'>\n'+('DEMO_'+tag.upper()+'\n')*40+'</'+tag+'>\n'
                              for tag in ['ca','cert','key'])

    def tearDown(self):
        self.db.close();self.engine.dispose()

    async def test_download_replaces_stale_directives_and_preserves_inline_material(self):
        for header in ['remote old.example.invalid 1194\nproto udp\n',
                       '  ReMoTe old.example.invalid 1194\n\tPrOtO udp\n']:
            with self.subTest(header=header):
                profile='client\ndev tun\n'+header+self.identity
                request=Mock()
                request.download_ovpn_client.return_value=Response(content=profile)
                with patch.object(task,'NodeRequests',return_value=request):
                    response=await task.download_ovpn_client_from_node('demo-profile-user',1,self.db)
                content=response.body.decode()
                directives=[line.strip() for line in content.splitlines()
                            if line.strip().split(' ',1)[0].lower() in {'remote','proto'}]
                self.assertEqual(directives,['remote vpn.example.invalid 443','proto tcp'])
                self.assertEqual(content.split('<ca>',1)[1],self.identity.split('<ca>',1)[1])
                self.assertIn('client\ndev tun\n',content)
                self.assertEqual(response.headers['cache-control'],'no-store')
                request.create_user.assert_not_called()

    async def test_invalid_profile_is_retried_but_never_returned_as_a_download(self):
        request=Mock();request.download_ovpn_client.return_value=Response(content='demo error')
        with patch.object(task,'NodeRequests',return_value=request):
            response=await task.download_ovpn_client_from_node('demo-profile-user',1,self.db)
        self.assertIsNone(response)
        request.create_user.assert_called_once_with('demo-user-demo-node')
        self.assertEqual(request.download_ovpn_client.call_count,2)
