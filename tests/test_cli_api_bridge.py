import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class CliApiBridgeTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        spec=importlib.util.spec_from_file_location('cli_api_bridge_test',ROOT/'scripts/pvnetwork_cli_api.py')
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)

    def tearDown(self):sys.path.remove(str(ROOT/'scripts'))

    def args(self,**values):
        return SimpleNamespace(command='nodes',action='list',node_id=7,job_id=None,input_json_stdin=False,lang='en',**values)

    def test_node_control_targets_only_registered_id_and_fixed_route(self):
        for action,drain in [('drain',True),('undrain',False)]:
            args=self.args();args.action=action
            with patch.object(self.module,'api',return_value={'id':7}) as api:
                self.module.nodes(args)
            self.assertEqual(api.call_args.args,('/nodes/7/control','PUT',{'drain':drain}))

    def test_edit_preserves_list_identity_tunnel_status_and_omits_key(self):
        node={'id':7,'name':'old','address':'node.example.invalid','tunnel-address':'vpn.example.invalid','protocol':'udp','ovpn_port':1194,'port':9443,'status':'inactive'}
        args=self.args();args.action='edit';args.input_json_stdin=True
        with patch.object(self.module,'api',side_effect=[[node],{'ok':True}]) as api,patch.object(self.module.sys,'stdin',io.StringIO(json.dumps({'name':'new'}))):
            self.module.nodes(args)
        path,method,payload=api.call_args.args
        self.assertEqual((path,method),('/nodes/7','PUT'));self.assertEqual(payload['name'],'new')
        self.assertEqual(payload['tunnel_address'],'vpn.example.invalid');self.assertFalse(payload['status']);self.assertNotIn('key',payload)

    def test_payload_must_be_bounded_object_and_rejects_unknown_key(self):
        args=self.args();args.input_json_stdin=True
        for content in ['[]','{"unknown":true}','x'*131073]:
            with self.subTest(content=content[:20]),patch.object(self.module.sys,'stdin',io.StringIO(content)),self.assertRaises(ValueError):
                self.module.input_payload(args,allowed={'name'})

    def test_panel_settings_secrets_are_body_only_and_not_returned(self):
        args=self.args();args.command='credentials';args.action='apply';args.input_json_stdin=True
        payload={'current_password':'private-old-demo','new_password':'private-new-demo'}
        with patch.object(self.module.sys,'stdin',io.StringIO(json.dumps(payload))),patch.object(self.module,'api',return_value={'change_id':'demo-id','change_token':'private-status-token','auth_token':'private-auth-token'}) as api:
            result=self.module.settings(args)
        self.assertEqual(api.call_args.args,('/security/panel-settings/apply','POST',payload))
        self.assertNotIn('private-',json.dumps(result));self.assertEqual(result['change_id'],'demo-id')

    def test_selected_session_diagnostic_uses_read_only_user_detail(self):
        args=SimpleNamespace(user_id='demo-user')
        with patch.object(self.module,'api',return_value={'success':True}) as api:
            self.module.sessions(args)
        self.assertEqual(api.call_args.args,('/users/demo-user/sessions',))
