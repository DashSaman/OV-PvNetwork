"""Node-scoped jobs expose no child output and recheck identity before spawn."""
import os
os.environ.setdefault('ADMIN_USERNAME','testadmin')
os.environ.setdefault('ADMIN_PASSWORD_HASH','test-only-hash')
os.environ.setdefault('JWT_SECRET_KEY','test-only-jwt-value-at-least-32-characters')
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.engine import Base
from backend.db.models import Node


class NodeReconcileJobTests(unittest.TestCase):
    def setUp(self):
        from backend.node import reconcile
        self.module=reconcile
        self.engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(self.engine)
        self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False);self.db=self.sessions()
        self.node=Node(id=7,name='demo',address='node.example.invalid',port=9443,key='private-demo-key',protocol='udp',ovpn_port=1194,status=True)
        self.db.add(self.node);self.db.commit()

    def tearDown(self):self.db.close();self.engine.dispose()

    def test_worker_uses_exact_script_and_node_id_and_discards_child_output(self):
        job=SimpleNamespace(state='queued',result={'operation':'node-reconcile','node_id':7},error=None)
        snapshot=self.module.snapshot(self.node)
        with patch.object(self.module,'SessionLocal',self.sessions),patch.object(self.module,'update_job'),patch.object(self.module,'fail_job') as fail,patch.object(self.module.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            self.module.run(job,snapshot)
        self.assertEqual(job.state,'succeeded');fail.assert_not_called()
        arguments=run.call_args.args[0];self.assertTrue(arguments[1].endswith('pvnetwork-node-user-reconcile.py'))
        self.assertEqual(arguments[-2:],['--node-id','7']);self.assertNotIn(self.node.key,str(run.call_args))
        self.assertEqual(run.call_args.kwargs['stdout'],self.module.subprocess.DEVNULL);self.assertEqual(run.call_args.kwargs['stderr'],self.module.subprocess.DEVNULL)

    def test_changed_credential_refuses_before_child_spawn(self):
        snapshot=self.module.snapshot(self.node);self.node.key='rotated-demo-key';self.db.commit()
        job=SimpleNamespace(state='queued',result={'operation':'node-reconcile','node_id':7})
        with patch.object(self.module,'SessionLocal',self.sessions),patch.object(self.module,'update_job'),patch.object(self.module,'fail_job') as fail,patch.object(self.module.subprocess,'run') as run:
            self.module.run(job,snapshot)
        run.assert_not_called();fail.assert_called_once();self.assertNotIn(self.node.key,str(fail.call_args))
