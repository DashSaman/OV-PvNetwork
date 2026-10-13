import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NodeInstallPreflightTests(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('native_node_install',ROOT/'scripts/pvnetwork_node_install.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def configuration(self,**values):
        return {'mode':'fresh','api_port':9090,'ovpn_port':1194,'protocol':'udp','host':'node.example.com','subnet':'10.44.0.0/24',**values}

    def facts(self,**values):
        return {'os_id':'ubuntu','os_version':'24.04','architecture':'x86_64','memory_kib':2*1024**2,'disk_free':8*1024**3,'listeners':set(),'openvpn_exists':False,'native_exists':False,'routes':[],**values}

    def test_foreign_api_listener_refused_before_install(self):
        with self.assertRaisesRegex(ValueError,'API port.*occupied'):self.module().preflight(self.configuration(),self.facts(listeners={('tcp',9090)}))

    def test_fresh_never_replaces_existing_openvpn(self):
        with self.assertRaisesRegex(ValueError,'adopt'):self.module().preflight(self.configuration(),self.facts(openvpn_exists=True))

    def test_adopt_requires_existing_runtime_and_free_agent_port(self):
        module=self.module()
        with self.assertRaisesRegex(ValueError,'existing OpenVPN'):module.preflight(self.configuration(mode='adopt'),self.facts())
        module.preflight(self.configuration(mode='adopt',api_port=9443),self.facts(openvpn_exists=True,listeners={('tcp',9090),('udp',1194)}))

    def test_unsupported_os_refused(self):
        with self.assertRaisesRegex(ValueError,'supported'):self.module().preflight(self.configuration(),self.facts(os_version='20.04'))

    def test_tcp_api_and_vpn_self_conflict_refused(self):
        with self.assertRaisesRegex(ValueError,'same TCP port'):self.module().preflight(self.configuration(protocol='tcp',ovpn_port=9090),self.facts())

    def test_existing_private_route_is_never_overwritten(self):
        with self.assertRaisesRegex(ValueError,'subnet.*conflict'):self.module().preflight(self.configuration(),self.facts(routes=['10.44.0.0/16']))

    def test_existing_tunnel_interface_is_never_adopted_by_fresh_install(self):
        with self.assertRaisesRegex(ValueError,'interface.*exists'):
            self.module().preflight(self.configuration(),self.facts(interfaces=['lo','pvn0']))

    def test_unverified_ipv6_source_is_refused_before_partial_firewall_installation(self):
        config=self.configuration(api_key='pvn_tls_v1_'+'x'*28,panel_url='https://panel.example.com',panel_source_ip='2001:db8::1')
        with self.assertRaisesRegex(ValueError,'IPv4'):
            self.module().config_values(config)

    def test_insufficient_memory_refused(self):
        with self.assertRaisesRegex(ValueError,'memory'):self.module().preflight(self.configuration(),self.facts(memory_kib=128*1024))

    def test_adopt_package_plan_never_upgrades_removes_or_reconfigures_installed_services(self):
        module=self.module()
        for plan in ['Inst openvpn [2.6.1] (2.6.2 Ubuntu)\n','Remv openvpn [2.6.1]\n','Conf openvpn (2.6.1 Ubuntu)\n']:
            with self.assertRaisesRegex(ValueError,'existing package'):
                module.validate_adopt_package_plan(plan,{'openvpn'})
        module.validate_adopt_package_plan('Inst tcpdump (4.99 Ubuntu)\nConf tcpdump (4.99 Ubuntu)\n',{'openvpn'})

    def test_rollback_stops_the_owned_network_service(self):
        from unittest.mock import patch
        module=self.module()
        record={'phase':'agent','created_files':['/etc/systemd/system/pvnetwork-node-network.service'],'configuration':{}}
        with patch.object(module,'run') as run,patch.object(module,'checkpoint'),patch.object(module.subprocess,'run'):
            module.rollback(record)
        self.assertIn(['systemctl','stop','pvnetwork-node-network'],[call.args[0] for call in run.call_args_list])

    def test_fresh_node_packages_preserve_existing_packages_and_services(self):
        from unittest.mock import patch
        module=self.module()
        installed=['ca-certificates','python3','python3-venv','openssl','socat','curl','iptables','iproute2','tcpdump','openvpn']
        status=''.join(name+'\tinstall ok installed\n' for name in installed)
        with patch.object(module,'run',side_effect=[status,'','Inst easy-rsa (3.1.6 Ubuntu)\nConf easy-rsa (3.1.6 Ubuntu)\n','']) as run:
            module.install_dependencies('fresh')
        install=run.call_args.args[0]
        self.assertIn('--no-upgrade',install);self.assertEqual(install[-1],'easy-rsa')
        self.assertNotIn('openvpn',install)
        self.assertEqual(run.call_args.kwargs['env']['NEEDRESTART_MODE'],'l')

    def test_preflight_cli_does_not_create_installed_state_or_lock(self):
        from unittest.mock import patch
        import contextlib,io,json,tempfile
        module=self.module()
        config=self.configuration(api_key='pvn_tls_v1_'+'x'*28,panel_url='https://panel.example.com',panel_source_ip='203.0.113.5')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);configuration=root/'config.json';configuration.write_text(json.dumps(config))
            state=root/'uncreated-state'
            with patch.object(module,'STATE',state),patch.object(module,'JOURNAL',state/'transaction.json'),patch.object(module,'validate_source'),patch.object(module,'host_facts',return_value=self.facts()),patch.object(module.os,'geteuid',return_value=0),patch.object(module.sys,'argv',['installer','--configuration',str(configuration),'--source',str(root),'--preflight']),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(),0)
            self.assertFalse(state.exists(),'preflight created installed state or lock')
