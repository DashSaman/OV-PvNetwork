import asyncio
import unittest
import tempfile
from pathlib import Path
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

    def test_missing_node_is_refused_before_any_remote_operation(self):
        db,node,request=self.fixture()
        with patch.object(task,'NodeRequests') as remote:
            self.assertFalse(asyncio.run(task.update_node_handler(node.id+999,request,db)))
            self.assertEqual(remote.call_count,0)
        db.close()

    def test_native_SQL_failure_requests_remote_rollback_and_preserves_row(self):
        db,node,request=self.fixture();before=self.values(node)
        with tempfile.TemporaryDirectory() as folder,patch.object(task.configuration,'ROOT',Path(folder)),patch.object(task,'NodeRequests') as remote:
            remote.return_value.get_node_info.return_value={'configuration_transaction':'v1'}
            remote.return_value.configuration_operation.side_effect=lambda action,identity:{'state':'ready' if action=='prepare' else 'rolled_back','transaction_id':identity}
            with patch.object(task.crud,'update_node',side_effect=RuntimeError('ci-SQL-commit-failure')):
                with self.assertRaisesRegex(RuntimeError,'SQL-commit-failure'):asyncio.run(task.update_node_handler(node.id,request,db))
            actions=[call.args[0] for call in remote.return_value.configuration_operation.call_args_list]
            self.assertEqual(actions,['prepare','rollback'])
            self.assertNotIn(request.key,''.join(path.read_text() for path in Path(folder).glob('*.json')))
        db.refresh(node);self.assertEqual(self.values(node),before);db.close()

    def test_native_finalize_observes_committed_controller_settings(self):
        db,node,request=self.fixture();node_id=node.id;before=self.values(node)
        def operation(action,identity):
            with Session(db.bind) as verify:
                row=verify.get(Node,node_id)
                if action=='prepare':self.assertEqual(self.values(row),before)
                elif action=='finalize':self.assertEqual(row.ovpn_port,1195)
            return {'state':'ready' if action=='prepare' else 'complete','transaction_id':identity}
        with tempfile.TemporaryDirectory() as folder,patch.object(task.configuration,'ROOT',Path(folder)),patch.object(task,'NodeRequests') as remote:
            remote.return_value.get_node_info.return_value={'configuration_transaction':'v1'}
            remote.return_value.configuration_operation.side_effect=operation
            self.assertTrue(asyncio.run(task.update_node_handler(node.id,request,db)))
            self.assertEqual([call.args[0] for call in remote.return_value.configuration_operation.call_args_list],['prepare','finalize'])
        db.close()

    def test_decision_distinguishes_running_SQL_old_row_and_committed_row(self):
        db,node,request=self.fixture()
        with tempfile.TemporaryDirectory() as folder,patch.object(task.configuration,'ROOT',Path(folder)):
            job=task.configuration.create(node,request)
            with task.configuration.running(job):
                self.assertEqual(task.configuration.decision(job,node),'pending')
                task.crud.update_node(db,node.id,request)
                self.assertEqual(task.configuration.decision(job,node),'finalize')
            stored=task.configuration.load(job['id'])
            self.assertFalse(stored['in_flight'])
            self.assertNotIn(node.key,str(stored))
        db.close()

    def test_authenticated_callback_returns_only_own_job_decision(self):
        from backend.routers import mirza
        from fastapi import HTTPException
        db,node,request=self.fixture()
        with tempfile.TemporaryDirectory() as folder,patch.object(task.configuration,'ROOT',Path(folder)):
            job=task.configuration.create(node,request)
            with self.assertRaises(HTTPException):mirza.node_configuration_decision(job['id'],'wrong-ci-key',db)
            result=mirza.node_configuration_decision(job['id'],node.key,db)
            self.assertEqual(result,{'transaction_id':job['id'],'decision':'rollback','controller':'pvnetwork-panel'})
            task.crud.update_node(db,node.id,request)
            self.assertEqual(mirza.node_configuration_decision(job['id'],node.key,db)['decision'],'finalize')
        db.close()

    def test_postcommit_refresh_failure_keeps_remote_new_settings(self):
        db,node,request=self.fixture();real_update=task.crud.update_node
        def committed_then_failed(*args):
            real_update(*args)
            raise RuntimeError('ci-postcommit-refresh-failure')
        with tempfile.TemporaryDirectory() as folder,patch.object(task.configuration,'ROOT',Path(folder)),patch.object(task,'NodeRequests') as remote:
            remote.return_value.get_node_info.return_value={'configuration_transaction':'v1'}
            remote.return_value.configuration_operation.side_effect=lambda action,identity:{'state':'ready' if action=='prepare' else 'complete','transaction_id':identity}
            with patch.object(task.crud,'update_node',side_effect=committed_then_failed):
                with self.assertRaisesRegex(RuntimeError,'postcommit-refresh'):asyncio.run(task.update_node_handler(node.id,request,db))
            self.assertNotIn('rollback',[call.args[0] for call in remote.return_value.configuration_operation.call_args_list])
        db.refresh(node);self.assertEqual(node.ovpn_port,1195);db.close()


if __name__=='__main__':unittest.main()
