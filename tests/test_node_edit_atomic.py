import asyncio
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from backend.db.models import Node
from backend.node import task
from backend.schema._input import NodeCreate


class NodeEditAtomicTests(unittest.TestCase):
    def fixture(self):
        engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Node.__table__.create(engine);db=Session(engine)
        node=Node(name='ci-node',address='node.example.com',tunnel_address='vpn.example.com',port=9090,key='x'*32,protocol='udp',ovpn_port=1194,status=True)
        db.add(node);db.commit();db.refresh(node)
        request=NodeCreate(name=node.name,address=node.address,tunnel_address='new-vpn.example.com',port=node.port,key=node.key,protocol='tcp',ovpn_port=1195,status=True)
        return db,node,request

    def values(self,node):return node.name,node.address,node.tunnel_address,node.protocol,node.ovpn_port,node.port,node.key,node.status

    def test_failed_remote_edit_preserves_controller_record(self):
        db,node,request=self.fixture();before=self.values(node)
        with patch.object(task,'NodeRequests') as remote:
            remote.return_value.check_node.return_value=False
            self.assertFalse(asyncio.run(task.update_node_handler(node.id,request,db)))
        db.refresh(node);self.assertEqual(self.values(node),before);db.close()

    def test_probe_exception_preserves_controller_record(self):
        db,node,request=self.fixture();before=self.values(node)
        with patch.object(task,'NodeRequests') as remote:
            remote.return_value.check_node.side_effect=RuntimeError('ci-probe-failure')
            with self.assertRaisesRegex(RuntimeError,'probe-failure'):
                asyncio.run(task.update_node_handler(node.id,request,db))
        db.refresh(node);self.assertEqual(self.values(node),before);db.close()

    def test_verified_edit_commits_after_remote_success(self):
        db,node,request=self.fixture();before=self.values(node)
        node_id=node.id
        def probe():
            with Session(db.bind) as verify:self.assertEqual(self.values(verify.get(Node,node_id)),before)
            return True
        with patch.object(task,'NodeRequests') as remote:
            remote.return_value.check_node.side_effect=probe
            self.assertTrue(asyncio.run(task.update_node_handler(node.id,request,db)))
        db.refresh(node);self.assertEqual(node.ovpn_port,1195);self.assertEqual(node.protocol,'tcp');db.close()


if __name__=='__main__':unittest.main()
