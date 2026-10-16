"""The legacy user-node CN includes the node name; edits must preserve it."""
import os
os.environ.setdefault('ADMIN_USERNAME','testadmin')
os.environ.setdefault('ADMIN_PASSWORD_HASH','test-only-hash')
os.environ.setdefault('JWT_SECRET_KEY','test-only-jwt-value-at-least-32-characters')
from datetime import date
import unittest
from unittest.mock import Mock,patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.engine import Base
from backend.db.models import Node,User,UserNode
from backend.node import task
from backend.schema._input import NodeUpdate


class NodeNameIdentityGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine,expire_on_commit=False)()
        self.node=Node(name='demo-node',address='node.example.invalid',protocol='udp',ovpn_port=1194,port=9443,key='private-demo-node-key',status=True)
        self.user=User(uuid='demo-user',name='alice',owner='demo-admin',total=0,used=0,expiry_date=date(2030,1,1),is_active=True,device_limit=1)
        self.db.add_all([self.node,self.user]);self.db.commit()

    def tearDown(self):self.db.close();self.engine.dispose()

    def request(self):
        return NodeUpdate(name='renamed-node',address=self.node.address,protocol='udp',ovpn_port=1194,port=9443,status=True)

    async def test_explicit_customer_assignment_refuses_name_change_before_remote_work(self):
        self.db.add(UserNode(user_uuid=self.user.uuid,node_id=self.node.id));self.db.commit()
        remote=Mock();remote.get_node_info.return_value={};remote.check_node.return_value=True
        with patch.object(task,'NodeRequests',return_value=remote) as factory,self.assertRaises(ValueError):
            await task.update_node_handler(self.node.id,self.request(),self.db)
        factory.assert_not_called();self.db.refresh(self.node);self.assertEqual(self.node.name,'demo-node')

    async def test_legacy_all_node_customer_also_preserves_certificate_name(self):
        remote=Mock();remote.get_node_info.return_value={};remote.check_node.return_value=True
        with patch.object(task,'NodeRequests',return_value=remote) as factory,self.assertRaises(ValueError):
            await task.update_node_handler(self.node.id,self.request(),self.db)
        factory.assert_not_called();self.db.refresh(self.node);self.assertEqual(self.node.name,'demo-node')

    async def test_customer_assigned_only_elsewhere_does_not_block_empty_node_edit(self):
        other=Node(name='other-node',address='other.example.invalid',protocol='udp',ovpn_port=1194,port=9443,key='private-other-demo-key',status=True)
        self.db.add(other);self.db.commit();self.db.add(UserNode(user_uuid=self.user.uuid,node_id=other.id));self.db.commit()
        remote=Mock();remote.get_node_info.return_value={};remote.check_node.return_value=True
        with patch.object(task,'NodeRequests',return_value=remote):self.assertTrue(await task.update_node_handler(self.node.id,self.request(),self.db))
        self.db.refresh(self.node);self.assertEqual(self.node.name,'renamed-node')
