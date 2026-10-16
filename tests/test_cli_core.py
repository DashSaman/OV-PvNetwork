"""CLI navigation and mutation gates run before any live-system operation."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stderr,redirect_stdout
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]


class CliCoreTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        spec=importlib.util.spec_from_file_location('pvnetwork_cli_test',ROOT/'scripts/pvnetwork_cli.py')
        self.cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.cli)

    def tearDown(self):sys.path.remove(str(ROOT/'scripts'))

    def invoke(self,args,stdin=None):
        out=io.StringIO();error=io.StringIO()
        with redirect_stdout(out),redirect_stderr(error),patch.object(self.cli.sys,'stdin',stdin or io.StringIO('')):
            status=self.cli.main(args)
        return status,out.getvalue(),error.getvalue()

    def test_exact_25_ordered_bilingual_menu_items(self):
        self.assertEqual([item['id'] for item in self.cli.MENU],list(range(1,26)))
        self.assertEqual(self.cli.MENU[-1]['command'],'exit')
        for item in self.cli.MENU:
            self.assertTrue(item['en']);self.assertRegex(item['fa'],r'[\u0600-\u06ff]')

    def test_noninteractive_no_arguments_gives_usage_without_runtime_access(self):
        with patch.object(self.cli,'dispatch') as dispatch:
            status,out,error=self.invoke([])
        self.assertEqual(status,64);dispatch.assert_not_called();self.assertIn('pvnetwork',out+error)

    def test_service_dry_run_never_executes_or_requires_confirmation(self):
        with patch.object(self.cli,'dispatch') as dispatch:
            status,out,error=self.invoke(['services','restart','--unit','pvnetwork-panel.service','--dry-run','--json'])
        self.assertEqual(status,0,error);dispatch.assert_not_called()
        value=json.loads(out);self.assertTrue(value['dry_run']);self.assertEqual(value['plan']['unit'],'pvnetwork-panel.service')

    def test_no_confirmation_or_root_fails_before_dispatch(self):
        with patch.object(self.cli,'dispatch') as dispatch,patch.object(self.cli.os,'geteuid',return_value=0,create=True):
            status,_,_=self.invoke(['services','restart','--unit','pvnetwork-panel.service'])
        self.assertEqual(status,77);dispatch.assert_not_called()
        with patch.object(self.cli,'dispatch') as dispatch,patch.object(self.cli.os,'geteuid',return_value=1000,create=True):
            status,_,_=self.invoke(['services','restart','--unit','pvnetwork-panel.service','--yes'])
        self.assertEqual(status,77);dispatch.assert_not_called()

    def test_forbidden_service_or_repair_scope_refused_before_dispatch(self):
        for args in [['services','restart','--unit','openvpn-server@server.service','--yes'],['repair','--scope','firewall','--yes']]:
            with self.subTest(args=args),patch.object(self.cli,'dispatch') as dispatch:
                status,_,_=self.invoke(args)
            self.assertEqual(status,64);dispatch.assert_not_called()

    def test_doctor_never_enters_mutation_gate(self):
        with patch.object(self.cli,'confirm') as confirm,patch.object(self.cli,'dispatch',return_value={'read_only':True}) as dispatch:
            status,out,error=self.invoke(['doctor','--json'])
        self.assertEqual(status,0,error);confirm.assert_not_called();dispatch.assert_called_once()
        self.assertTrue(json.loads(out)['data']['read_only'])

    def test_argument_and_unexpected_runtime_errors_never_echo_input_secrets(self):
        status,out,error=self.invoke(['doctor','--private-fixture','do-not-print-demo-secret'])
        self.assertEqual(status,64);self.assertNotIn('do-not-print-demo-secret',out+error)
        with patch.object(self.cli,'dispatch',side_effect=TypeError('private-fixture-value')):
            status,out,error=self.invoke(['doctor','--json'])
        self.assertEqual(status,70);self.assertNotIn('private-fixture-value',out+error)

    def test_unhealthy_doctor_exits_nonzero_and_invalid_restore_never_dispatches(self):
        with patch.object(self.cli,'dispatch',return_value={'healthy':False}):
            status,out,_=self.invoke(['doctor','--json'])
        self.assertEqual(status,69);self.assertFalse(json.loads(out)['success'])
        with patch.object(self.cli,'dispatch') as dispatch:
            status,_,_=self.invoke(['restore','../../foreign','--yes'])
        self.assertEqual(status,64);dispatch.assert_not_called()

    def test_existing_native_json_result_shape_is_preserved(self):
        for command,result in [('backup',{'backup':'/private/native-backup','verified':True}),('version',{'version':'1.0.44'})]:
            with self.subTest(command=command),patch.object(self.cli,'dispatch',return_value=result),patch.object(self.cli.os,'geteuid',return_value=0,create=True):
                status,out,error=self.invoke([command,'--json'])
            self.assertEqual(status,0,error);self.assertEqual(json.loads(out),result)

    def test_node_repair_requires_explicit_positive_target_even_for_dry_run(self):
        with patch.object(self.cli,'dispatch') as dispatch:
            status,_,_=self.invoke(['repair','--scope','node-reconcile','--dry-run'])
        self.assertEqual(status,64);dispatch.assert_not_called()
        status,out,error=self.invoke(['repair','--scope','node-reconcile','--node-id','7','--dry-run','--json'])
        self.assertEqual(status,0,error);self.assertEqual(json.loads(out)['plan']['node_id'],7)
