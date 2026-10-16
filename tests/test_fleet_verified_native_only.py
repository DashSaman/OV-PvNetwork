import asyncio
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.db.models import Node
from backend.routers import fleet


class VerifiedFleetTests(unittest.TestCase):
    def fixture(self):
        engine=create_engine('sqlite://')
        Node.__table__.create(engine)
        db=Session(engine)
        node=Node(name='demo-old',address='node.example.com',port=9090,key='x'*32,protocol='udp',ovpn_port=1194,status=True,drain=False,maintenance=False)
        db.add(node);db.commit()
        return db,node

    def test_legacy_upgrade_refuses_before_flags_or_remote_commands(self):
        db,node=self.fixture()
        job={'id':'ci-demo','node_ids':[node.id],'completed':{},'ssh_username':'root','ssh_port':22}
        with patch.object(fleet,'SessionLocal',return_value=db),patch.object(fleet,'save'),patch.object(fleet,'is_native',return_value=False),patch.object(fleet,'ssh',side_effect=AssertionError('unsafe legacy SSH upgrade invoked')) as ssh:
            fleet.run(job,'ci-demo-password')
            self.assertEqual(ssh.call_count,0,'legacy upgrade invoked an unverified remote command')
        with Session(db.bind) as verify:
            stored=verify.get(Node,node.id)
            self.assertFalse(stored.maintenance);self.assertFalse(stored.drain)
        self.assertEqual(job['state'],'failed');self.assertIn('adopt',job['error'].lower())

    def test_legacy_rollback_refuses_before_flags_or_remote_commands(self):
        db,node=self.fixture()
        request=fleet.RollbackRequest(ssh_password='ci-demo-password')
        with patch.object(fleet,'is_native',return_value=False),patch.object(fleet,'ssh') as ssh:
            with self.assertRaises(HTTPException) as failure:
                asyncio.run(fleet.rollback_node(node.id,request,db,{'type':'main_admin'}))
            self.assertEqual(failure.exception.status_code,409)
            ssh.assert_not_called()
        db.refresh(node);self.assertFalse(node.maintenance);self.assertFalse(node.drain)
        db.close()

    def test_canary_cannot_expand_the_requested_node_scope(self):
        db,node=self.fixture()
        outside=Node(name='demo-outside',address='outside.example.com',port=9443,key='y'*32,protocol='udp',ovpn_port=1194,status=True)
        db.add(outside);db.commit();outside_id=outside.id
        job={'id':'ci-demo','node_ids':[node.id],'canary_node_id':outside_id,'completed':{},'ssh_username':'root','ssh_port':22}
        with patch.object(fleet,'SessionLocal',return_value=db),patch.object(fleet,'save'),patch.object(fleet,'is_native',return_value=True),patch.object(fleet,'NodeRequests') as requests,patch.object(fleet,'native_operation',return_value={'version':'1.0.43'}) as operation:
            requests.return_value.get_node_info.return_value={'version':'0.0.0','status':'running'}
            fleet.run(job,'ci-demo-password');operation.assert_not_called()
        self.assertEqual(job['state'],'failed');self.assertIn('canary',job['error'].lower())
        with Session(db.bind) as verify:self.assertIsNone(verify.get(Node,outside_id).last_upgrade_at)

    def test_native_upgrade_keeps_administrative_flags_and_uses_verified_operation(self):
        db,node=self.fixture();node_id=node.id
        node.maintenance=True;node.drain=True;db.commit()
        job={'id':'ci-demo','node_ids':[node_id],'completed':{},'ssh_username':'root','ssh_port':22,'ssh_fingerprints':{str(node_id):'ci-pinned'}}
        with patch.object(fleet,'SessionLocal',return_value=db),patch.object(fleet,'save'),patch.object(fleet,'is_native',return_value=True),patch.object(fleet,'NodeRequests') as requests,patch.object(fleet,'native_operation',return_value={'version':'1.0.43'}) as operation,patch.object(fleet,'ssh') as legacy:
            requests.return_value.get_node_info.return_value={'version':'0.0.0','status':'running'}
            fleet.run(job,'ci-demo-password')
            self.assertEqual(operation.call_count,1);legacy.assert_not_called()
            self.assertEqual(operation.call_args.args[1],'upgrade');self.assertEqual(operation.call_args.args[-1],'ci-pinned')
        self.assertEqual(job['state'],'succeeded')
        with Session(db.bind) as verify:
            stored=verify.get(Node,node_id);self.assertTrue(stored.maintenance);self.assertTrue(stored.drain)

    def test_legacy_endpoint_returns_actionable_conflict_without_launching(self):
        db,node=self.fixture()
        request=fleet.Upgrade(node_ids=[node.id],ssh_password='ci-demo-password')
        with patch.object(fleet,'is_native',return_value=False),patch.object(fleet,'save') as save,patch.object(fleet,'launch') as launch:
            with self.assertRaises(HTTPException) as failure:
                asyncio.run(fleet.upgrade(request,{'type':'main_admin'},db))
            self.assertEqual(failure.exception.status_code,409)
            self.assertIn('Adopt Existing Node',failure.exception.detail)
            save.assert_not_called();launch.assert_not_called()
        db.close()


if __name__=='__main__':unittest.main()
