"""Authorization and job binding are enforced before exposing node operations."""
import os
os.environ.setdefault('ADMIN_USERNAME','testadmin')
os.environ.setdefault('ADMIN_PASSWORD_HASH','test-only-hash')
os.environ.setdefault('JWT_SECRET_KEY','test-only-jwt-value-at-least-32-characters')
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from fastapi import HTTPException


class NodeReconcileRouteTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).resolve().parents[1]/'backend/routers/node_operations.py'
        spec=importlib.util.spec_from_file_location('node_operations_test',path)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.db=Mock();self.db.get.return_value=SimpleNamespace(id=7)

    def test_non_main_admin_denied_before_node_lookup_or_queue(self):
        with patch.object(self.module.reconcile,'start') as start:
            with self.assertRaises(HTTPException) as error:self.module.reconcile_node(7,{'type':'admin'},self.db)
        self.assertEqual(error.exception.status_code,403);start.assert_not_called();self.db.get.assert_not_called()

    def test_missing_node_cannot_queue(self):
        self.db.get.return_value=None
        with patch.object(self.module.reconcile,'start') as start:
            with self.assertRaises(HTTPException) as error:self.module.reconcile_node(7,{'type':'main_admin'},self.db)
        self.assertEqual(error.exception.status_code,404);start.assert_not_called()

    def test_status_rejects_other_node_and_operation(self):
        for result in [{'operation':'node-reconcile','node_id':8},{'operation':'backup','node_id':7},None]:
            with self.subTest(result=result),patch.object(self.module,'get_deploy_job',return_value={'result':result}):
                with self.assertRaises(HTTPException) as error:self.module.reconcile_status(7,'demo-job',{'type':'main_admin'},self.db)
                self.assertEqual(error.exception.status_code,404)
        job={'result':{'operation':'node-reconcile','node_id':7},'state':'succeeded'}
        with patch.object(self.module,'get_deploy_job',return_value=job):
            self.assertEqual(self.module.reconcile_status(7,'demo-job',{'type':'main_admin'},self.db).data,job)
