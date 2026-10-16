import os
import base64
import socket
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('ADMIN_USERNAME', 'ci-admin')
os.environ.setdefault('ADMIN_PASSWORD_HASH', '$2b$12$abcdefghijklmnopqrstuu1234567890123456789012')
os.environ.setdefault('JWT_SECRET_KEY', 'ci-private-demo-jwt-secret-over-32-characters')


class PushTransportTests(unittest.TestCase):
    def module(self):
        from backend.operations import push_transport
        return push_transport

    def test_only_supported_or_operator_approved_canonical_https_origins(self):
        module = self.module()
        for url in ['https://fcm.googleapis.com/fcm/send/demo',
                    'https://updates.push.services.mozilla.com/wpush/v2/demo',
                    'https://web.push.apple.com/demo', 'https://region.push.apple.com/demo',
                    'https://wns1.notify.windows.com/demo']:
            self.assertEqual(module.validate_endpoint(url), url)
        with patch.object(module.config, 'PUSH_ALLOWED_ORIGINS', 'https://push.example.org:8443'):
            self.assertEqual(module.validate_endpoint('https://push.example.org:8443/demo'), 'https://push.example.org:8443/demo')
        with patch.object(module.config, 'PUSH_ALLOWED_ORIGINS', 'https://region.push.apple.com'):
            with self.assertRaises(ValueError): module.validate_endpoint('https://evil.invalid/demo')
        for url in ['http://fcm.googleapis.com/demo', 'https://127.0.0.1/demo',
                    'https://[::1]/demo', 'https://fcm.googleapis.com.evil.invalid/demo',
                    'https://fcm.googleapis.com@evil.invalid/demo', 'https://fcm.googleapis.com./demo',
                    'https://fcm.googleapis.com:444/demo', 'https://fcm.googleapis.com/demo#frag',
                    'https://fcm.googleapis.com\\@evil.invalid/demo', 'https://fcm.googleapis.com/\r\nDemo',
                    'https://FCM.GOOGLEAPIS.COM/demo', 'https://fcm.googleapis.com/%0d%0aDemo',
                    'https://evilpush.apple.com/demo', 'https://web.push.apple.com.evil.invalid/demo',
                    'https://wns1.notify.windows.com:8443/demo']:
            with self.subTest(url=url), self.assertRaises(ValueError): module.validate_endpoint(url)

    def test_transport_rejects_private_mixed_and_rebound_dns(self):
        module = self.module()
        for ips in [('127.0.0.1',), ('10.0.0.1',), ('169.254.169.254',), ('::1',),
                    ('::ffff:127.0.0.1',), ('8.8.8.8', '192.168.1.1')]:
            records = [(socket.AF_INET6 if ':' in ip else socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443)) for ip in ips]
            with self.subTest(ips=ips), patch.object(module.socket, 'getaddrinfo', return_value=records), self.assertRaises(ValueError):
                module.PushSession().post('https://fcm.googleapis.com/demo', data=b'test', headers={}, timeout=12)

    def test_connection_pins_validated_ip_tls_hostname_and_disables_redirects_retries(self):
        module = self.module()
        records = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
        response = SimpleNamespace(status=307, reason='redirect', headers={'Location': 'http://127.0.0.1/'},
                                   read=lambda *_a, **_k: b'', close=lambda: None, release_conn=lambda: None)
        pool = SimpleNamespace(urlopen=lambda *a, **kw: response, close=lambda: None)
        from unittest.mock import Mock
        pool.urlopen = Mock(return_value=response)
        with patch.object(module.socket, 'getaddrinfo', return_value=records) as dns, patch.object(module, 'HTTPSConnectionPool', return_value=pool) as factory:
            result = module.PushSession().post('https://fcm.googleapis.com/demo?x=1', data=b'ciphertext', headers={'Authorization': 'demo'}, timeout=12)
        self.assertEqual(result.status_code, 307)
        self.assertEqual(dns.call_count, 1)
        self.assertEqual(factory.call_args.args[0], '8.8.8.8')
        self.assertEqual(factory.call_args.kwargs['assert_hostname'], 'fcm.googleapis.com')
        self.assertEqual(factory.call_args.kwargs['server_hostname'], 'fcm.googleapis.com')
        self.assertEqual(pool.urlopen.call_args.args[:2], ('POST', '/demo?x=1'))
        self.assertFalse(pool.urlopen.call_args.kwargs['redirect'])
        self.assertFalse(pool.urlopen.call_args.kwargs['retries'])
        self.assertEqual(pool.urlopen.call_args.kwargs['headers']['Host'], 'fcm.googleapis.com')

    def test_shared_sender_always_injects_guarded_transport_for_stored_rows(self):
        module = self.module()
        with patch.object(module, '_webpush') as send:
            module.send_push(subscription_info={'endpoint':'https://web.push.apple.com/demo','keys':{}}, data='demo')
        self.assertIsInstance(send.call_args.kwargs['requests_session'], module.PushSession)
        self.assertEqual(send.call_args.kwargs['timeout'], 12)
        with patch.object(module, '_webpush') as send, self.assertRaises(ValueError):
            module.send_push(subscription_info={'endpoint':'https://127.0.0.1/demo','keys':{}}, data='demo')
        send.assert_not_called()

    def test_real_webpush_encryption_and_vapid_use_the_guarded_session(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        from py_vapid import Vapid
        from unittest.mock import Mock
        module=self.module()
        key=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        encode=lambda value:base64.urlsafe_b64encode(value).decode().rstrip('=')
        info={'endpoint':'https://fcm.googleapis.com/fcm/send/demo',
              'keys':{'p256dh':encode(key),'auth':encode(os.urandom(16))}}
        vapid=Vapid();vapid.generate_keys()
        raw=SimpleNamespace(status=201,reason='Created',headers={},read=lambda *_a,**_k:b'',
                            close=lambda:None,release_conn=lambda:None)
        pool=SimpleNamespace(urlopen=Mock(return_value=raw),close=lambda:None)
        records=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))]
        with patch.object(module.socket,'getaddrinfo',return_value=records),patch.object(module,'HTTPSConnectionPool',return_value=pool):
            result=module.send_push(subscription_info=info,data='private demo notification',
                vapid_private_key=vapid,vapid_claims={'sub':'mailto:demo@example.invalid'},ttl=120)
        self.assertEqual(result.status_code,201)
        sent=pool.urlopen.call_args.kwargs
        self.assertIsInstance(sent['body'],bytes)
        self.assertNotIn(b'private demo notification',sent['body'])
        self.assertTrue(any(name.lower()=='authorization' for name in sent['headers']))
