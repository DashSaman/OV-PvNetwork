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

    def test_insufficient_memory_refused(self):
        with self.assertRaisesRegex(ValueError,'memory'):self.module().preflight(self.configuration(),self.facts(memory_kib=128*1024))

    def test_adopt_package_plan_never_upgrades_removes_or_reconfigures_installed_services(self):
        module=self.module()
        for plan in ['Inst openvpn [2.6.1] (2.6.2 Ubuntu)\n','Remv openvpn [2.6.1]\n','Conf openvpn (2.6.1 Ubuntu)\n']:
            with self.assertRaisesRegex(ValueError,'existing package'):
                module.validate_adopt_package_plan(plan,{'openvpn'})
        module.validate_adopt_package_plan('Inst tcpdump (4.99 Ubuntu)\nConf tcpdump (4.99 Ubuntu)\n',{'openvpn'})
