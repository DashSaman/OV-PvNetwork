"""Explicit reconciliation must never widen the requested node scope."""
import os
os.environ.setdefault('ADMIN_USERNAME','testadmin')
os.environ.setdefault('ADMIN_PASSWORD_HASH','test-only-hash')
os.environ.setdefault('JWT_SECRET_KEY','test-only-jwt-value-at-least-32-characters')
import importlib.util
import io
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.engine import Base
from backend.db.models import Node,User,UserNode

ROOT=Path(__file__).resolve().parents[1]


class ScopedNodeReconcileTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('scoped_reconcile_test',ROOT/'scripts/pvnetwork-node-user-reconcile.py')
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine,expire_on_commit=False)()
        self.nodes=[Node(name='demo-a',address='a.example.invalid',port=9443,key='private-demo-a',protocol='udp',ovpn_port=1194,status=True),
            Node(name='demo-b',address='b.example.invalid',port=9443,key='private-demo-b',protocol='udp',ovpn_port=1194,status=True,drain=True)]
        self.users=[User(uuid='demo-a',name='alice',owner='demo',total=0,used=0,expiry_date=date(2030,1,1),is_active=True,device_limit=1),
            User(uuid='demo-b',name='bob',owner='demo',total=0,used=0,expiry_date=date(2030,1,1),is_active=True,device_limit=1)]
        self.db.add_all([*self.nodes,*self.users]);self.db.commit()
        self.db.add_all([UserNode(user_uuid=self.users[0].uuid,node_id=self.nodes[0].id),UserNode(user_uuid=self.users[1].uuid,node_id=self.nodes[1].id)]);self.db.commit()

    def tearDown(self):self.db.close();self.engine.dispose()

    def test_explicit_node_repair_keeps_drain_and_only_its_assignments(self):
        remote=Mock();remote.check_node.return_value=True;seen=[]
        with patch.object(self.module,'SessionLocal',return_value=self.db),patch.object(self.module,'NodeRequests',return_value=remote) as factory,patch.object(self.module,'profile_valid',side_effect=lambda _client,name:seen.append(name) or True),redirect_stdout(io.StringIO()):
            result=self.module.main(self.nodes[1].id)
        self.assertEqual(result,0);self.assertEqual(factory.call_count,1);self.assertEqual(factory.call_args.kwargs['address'],'b.example.invalid')
        self.assertEqual(seen,['bob-demo-b']);self.assertEqual(self.db.query(UserNode).count(),2)
        self.assertTrue(self.db.get(Node,self.nodes[1].id).drain);remote.create_user.assert_not_called()

    def test_missing_target_fails_before_remote_calls(self):
        with patch.object(self.module,'SessionLocal',return_value=self.db),patch.object(self.module,'NodeRequests') as factory,redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main(9999),1)
        factory.assert_not_called()
