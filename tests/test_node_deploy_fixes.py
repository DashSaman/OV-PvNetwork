"""Source allowlist regressions now exercise the native installer seam."""
import importlib.util
import inspect
from pathlib import Path
from unittest import TestCase,mock
from backend.node.deploy import _panel_firewall_mode,deploy_node

ROOT=Path(__file__).resolve().parents[1]


class PanelSourceAutodetectTests(TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('test_node_firewall',ROOT/'scripts/pvnetwork_node_install.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def test_mode_classifier_preserves_explicit_ip_and_hostname_autodetection(self):
        self.assertEqual(('explicit','203.0.113.5'),_panel_firewall_mode('203.0.113.5'))
        self.assertEqual(('explicit','2001:db8::1'),_panel_firewall_mode('2001:db8::1'))
        for value in [None,'','panel.example.com']:
            self.assertEqual(('auto',''),_panel_firewall_mode(value))

    def test_scoped_rules_keep_loopback_hook_access_and_allow_only_controller(self):
        module=self.module();record={'id':'demo','phase':'agent'}
        with mock.patch.object(module,'checkpoint'),mock.patch.object(module,'run') as run:
            module.api_firewall({'panel_source_ip':'203.0.113.5','api_port':9443},record)
        commands=[c.args[0] for c in run.call_args_list]
        self.assertEqual(len(commands),3)
        self.assertTrue(all(c[0]=='iptables' and c[2]=='-A' for c in commands))
        self.assertIn('lo',commands[0]);self.assertIn('203.0.113.5',commands[1]);self.assertEqual(commands[-1][-1],'DROP')
        self.assertTrue(all('9443' in c and '--comment' in c for c in commands))
        self.assertFalse(any('-F' in c or '-P' in c or 'systemctl' in c for c in commands))

    def test_ipv6_controller_gets_ipv6_scoped_rules(self):
        module=self.module()
        with mock.patch.object(module,'checkpoint'),mock.patch.object(module,'run') as run:
            module.api_firewall({'panel_source_ip':'2001:db8::1','api_port':9443},{'id':'demo','phase':'agent'})
        self.assertTrue(all(c.args[0][0]=='ip6tables' for c in run.call_args_list))

    def test_optional_source_ip_keeps_the_public_request_contract(self):
        self.assertIs(inspect.signature(deploy_node).parameters['panel_ip'].default,None)
        from backend.node.native_deploy import BOOTSTRAP
        self.assertIn('SSH_CONNECTION',BOOTSTRAP);self.assertIn('SSH_CLIENT',BOOTSTRAP)

    def test_existing_install_script_download_is_absent_from_deployment(self):
        source=(ROOT/'backend/node/deploy.py').read_text()
        self.assertNotIn('curl -sSL https://astral.sh',source)
        self.assertNotIn('openvpn-install.sh',source)
        self.assertNotIn('_domain_payload',source)

    def test_node_verify_does_not_apply_or_restart_vpn_settings(self):
        source=(ROOT/'backend/routers/node.py').read_text()
        function=source.split('def _verify_node_from_panel(',1)[1].split('# PVNETWORK_AUTO_SYNC_NEW_NODE',1)[0]
        self.assertIn('set_new_setting=False',function)
        self.assertNotIn('set_new_setting=True',function)

    def test_add_node_has_optional_source_ip_and_password_or_key(self):
        source=(ROOT/'frontend/src/components/AddNodeModal.jsx').read_text(encoding='utf-8')
        for value in ['addNodePanelIpHelp','ssh_private_key','controller_url','panel_ip.trim() ? formData.panel_ip.trim() : null']:
            self.assertIn(value,source)
