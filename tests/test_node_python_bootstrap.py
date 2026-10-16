"""Minimal Python prerequisite does not interpolate credentials or upgrade hosts."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import shutil
import sys


class NodePythonBootstrapTests(unittest.TestCase):
    def command(self, **values):
        from backend.node.native_deploy import bootstrap_command
        return bootstrap_command('root', 'print("fixed-source")', {
            'mode':'fresh','api_port':9443,'ovpn_port':1194,'protocol':'udp',
            'api_key':'private-fixture-do-not-copy',**values})

    def test_invalid_preflight_arguments_never_enter_remote_shell(self):
        for values in [{'mode':'fresh; touch /tmp/wrong'}, {'api_port':True},
                       {'api_port':'9443;bad'}, {'protocol':'udp\ncommand'}, {'ovpn_port':0}]:
            with self.subTest(values=values),self.assertRaises(ValueError):self.command(**values)

    def test_command_contains_only_scoped_parameters_and_fixed_source(self):
        from backend.node.native_deploy import bootstrap_command, PYTHON_BOOTSTRAP
        command=bootstrap_command('operator','fixed-code',{'mode':'adopt','api_port':9443,'ovpn_port':1194,'protocol':'tcp','api_key':'private-fixture'})
        self.assertTrue(command.startswith('sudo -n sh -c '))
        self.assertNotIn('private-fixture',command)
        self.assertIn('--no-upgrade',PYTHON_BOOTSTRAP)
        self.assertIn('--no-remove',PYTHON_BOOTSTRAP)
        self.assertNotIn('systemctl restart',PYTHON_BOOTSTRAP)
        self.assertNotIn('curl ',PYTHON_BOOTSTRAP)

    @unittest.skipUnless(os.name=='posix','POSIX prerequisite execution requires Linux')
    def test_existing_python_executes_without_package_manager_and_preserves_stdin(self):
        from backend.node.native_deploy import bootstrap_command
        code='import json,sys;v=json.load(sys.stdin);assert v=={"fixture":"secret-only-stdin"};print("verified")'
        command=bootstrap_command('root',code,{'mode':'fresh','api_port':9443,'ovpn_port':1194,'protocol':'udp'})
        with tempfile.TemporaryDirectory() as folder:
            apt=Path(folder)/'apt-get';apt.write_text('#!/bin/sh\nexit 91\n');apt.chmod(0o755)
            result=subprocess.run(['sh','-c',command],input='{"fixture":"secret-only-stdin"}',env={**os.environ,'PATH':folder+':'+os.environ['PATH']},capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'verified')

    def missing_python_fixture(self, plan, *, port_busy=False):
        from backend.node.native_deploy import PYTHON_BOOTSTRAP
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);binpath=root/'bin';binpath.mkdir()
            for name in ['awk','cat','chmod','rm','mktemp']:
                (binpath/name).symlink_to(shutil.which(name))
            def executable(name, content):
                p=binpath/name;p.write_text('#!/bin/sh\n'+content);p.chmod(0o755)
            executable('id','echo 0\n');executable('uname','echo x86_64\n')
            executable('df','printf "Filesystem 1024-blocks Used Available Capacity Mounted\\nfixture 9999999 0 9999999 0 /opt\\n"\n')
            executable('dpkg','exit 0\n')
            executable('dpkg-query','printf "base-files\\tinstall ok installed\\n"\n')
            executable('apt-get','printf "%s\\n" "$*" >> '+str(root/'calls')+'\n'
                       +'case "$1" in update) exit 0 ;; -s) cat '+str(root/'plan')+'; exit 0 ;; esac\n'
                       +'ln_target='+str(binpath/'python3')+'\n'
                       +'/bin/ln -s '+sys.executable+' "$ln_target"\n')
            (root/'plan').write_text(plan)
            (root/'os-release').write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
            (root/'systemd').mkdir();(root/'opt').mkdir();(root/'vpn').mkdir()
            (root/'meminfo').write_text('MemTotal: 2097152 kB\n')
            (root/'net').mkdir()
            (root/'net/tcp').write_text('header\n'+('0: 00000000:24E3 00000000:0000 0A\n' if port_busy else ''))
            script=PYTHON_BOOTSTRAP.replace('/etc/os-release',str(root/'os-release')).replace('/run/systemd/system',str(root/'systemd'))
            script=script.replace('/dev/net/tun','/dev/null').replace('/proc/meminfo',str(root/'meminfo')).replace('df -Pk /opt','df -Pk '+str(root/'opt'))
            script=script.replace('/opt/pvnetwork-node',str(root/'native')).replace('/sys/class/net/pvn0',str(root/'interface'))
            script=script.replace('/etc/openvpn/server/',str(root/'vpn')+'/').replace('/proc/net/',str(root/'net')+'/')
            code='import sys;assert sys.stdin.read()=="stdin-preserved";print("verified")'
            result=subprocess.run(['/bin/sh','-c',script,'fixture',code,'fresh','9443','1194','udp'],input='stdin-preserved',env={'PATH':str(binpath)},capture_output=True,text=True,timeout=10)
            calls=(root/'calls').read_text() if (root/'calls').exists() else ''
            return result,calls

    @unittest.skipUnless(os.name=='posix','POSIX prerequisite execution requires Linux')
    def test_missing_python_only_installs_after_safe_simulation(self):
        result,calls=self.missing_python_fixture('Inst python3 (3.12 Ubuntu)\nConf python3 (3.12 Ubuntu)\n')
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertIn('verified',result.stdout)
        self.assertEqual(len(calls.splitlines()),3)
        self.assertIn('--no-upgrade --no-remove --no-install-recommends install -y python3',calls)

    @unittest.skipUnless(os.name=='posix','POSIX prerequisite execution requires Linux')
    def test_existing_package_change_or_removal_never_reaches_install(self):
        for plan in ['Inst base-files [1] (2 Ubuntu)\n','Conf base-files (1 Ubuntu)\n','Remv foreign-service [1]\n']:
            with self.subTest(plan=plan):
                result,calls=self.missing_python_fixture(plan)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(len(calls.splitlines()),2)
                self.assertNotIn('verified',result.stdout)

    @unittest.skipUnless(os.name=='posix','POSIX prerequisite execution requires Linux')
    def test_busy_api_port_refused_before_any_package_command(self):
        result,calls=self.missing_python_fixture('Inst python3 (3.12 Ubuntu)\n',port_busy=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(calls,'')
