"""An edit round-trip must not require exporting the node's stored credential."""
import os
os.environ.setdefault('ADMIN_USERNAME','testadmin')
os.environ.setdefault('ADMIN_PASSWORD_HASH','test-only-hash')
os.environ.setdefault('JWT_SECRET_KEY','test-only-jwt-value-at-least-32-characters')
import inspect
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.engine import Base
from backend.db.models import Node
from backend.node import task,configuration
from backend.routers import node as router


class NodeEditCredentialTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine,expire_on_commit=False)()
        self.node=Node(name='demo-old',address='node.example.invalid',tunnel_address='vpn.example.invalid',protocol='udp',ovpn_port=1194,port=9443,key='legacy-private-demo-'+'x'*80,status=True)
        self.db.add(self.node);self.db.commit()
        self.folder=tempfile.TemporaryDirectory();self.override=patch.object(configuration,'ROOT',Path(self.folder.name)/'configuration');self.override.start()
        self.payload={'name':'demo-renamed','address':self.node.address,'tunnel_address':self.node.tunnel_address,'port':9443,'ovpn_port':1194,'protocol':'udp','status':True,'set_new_setting':True}

    def tearDown(self):
        self.override.stop();self.folder.cleanup();self.db.close();self.engine.dispose()

    def request(self,**values):
        schema=inspect.signature(router.update_node).parameters['request'].annotation
        return schema(**self.payload,**values)

    async def test_node_list_exposes_canonical_tunnel_alias_without_exporting_key(self):
        rows=await task.list_nodes_handler(self.db)
        self.assertEqual(rows[0]['tunnel_address'],self.node.tunnel_address)
        self.assertEqual(rows[0]['tunnel-address'],self.node.tunnel_address)
        self.assertNotIn('key',rows[0]);self.assertNotIn(self.node.key,str(rows))

    async def test_omitted_or_blank_key_preserves_long_stored_credential_and_identity(self):
        original_key=self.node.key;identity=self.node.id
        for fields in [{},{'key':''},{'key':None}]:
            with self.subTest(fields=fields):
                request=self.request(**fields)
                remote=Mock();remote.get_node_info.return_value={'configuration_transaction':'v1'}
                remote.configuration_operation.side_effect=lambda action,*_: {'state':'ready','transaction_id':'a'*24} if action=='prepare' else {'state':'complete'}
                with patch.object(task,'NodeRequests',return_value=remote) as factory:
                    self.assertTrue(await task.update_node_handler(identity,request,self.db))
                self.assertEqual(factory.call_args.kwargs['api_key'],original_key)
                self.db.expire_all();saved=self.db.get(Node,identity)
                self.assertEqual(saved.key,original_key);self.assertEqual(saved.id,identity)
                self.assertEqual(saved.tunnel_address,self.payload['tunnel_address']);self.assertEqual(saved.name,'demo-renamed')

    async def test_explicit_replacement_still_uses_the_supplied_credential(self):
        request=self.request(key='replacement-demo-key')
        remote=Mock();remote.get_node_info.return_value={};remote.check_node.return_value=False
        with patch.object(task,'NodeRequests',return_value=remote) as factory:
            self.assertFalse(await task.update_node_handler(self.node.id,request,self.db))
        self.assertEqual(factory.call_args.kwargs['api_key'],'replacement-demo-key')
        self.db.refresh(self.node);self.assertNotEqual(self.node.key,'replacement-demo-key')
