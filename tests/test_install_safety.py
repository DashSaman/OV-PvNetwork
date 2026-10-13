"""Executable bootstrap failures and fresh-host preflight boundaries."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('bash') and os.name == 'posix', 'requires executable Linux Bash')
class BootstrapSafetyTests(unittest.TestCase):
    def run_bootstrap(self, *, checksum_ok=True, version='1.0.41', extra=None):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            archive = base/'fixture.tar.gz'
            payloads = {'VERSION':version+'\n','manifest.json':json.dumps({'version':version}),
                        'frontend/package.json':json.dumps({'version':version}),
                        'main.py':'# fixture\n','install-local.sh':'#!/bin/bash\nprintf invoked > "$MARKER"\n'}
            with tarfile.open(archive,'w:gz') as tar:
                for name, text in payloads.items():
                    data=text.encode(); info=tarfile.TarInfo('release/'+name)
                    info.size=len(data);info.mode=0o755 if name.endswith('.sh') else 0o644
                    tar.addfile(info,io.BytesIO(data))
                if extra:
                    info=tarfile.TarInfo(extra[0]);info.type=extra[1];info.linkname=extra[2]
                    tar.addfile(info)
            digest=hashlib.sha256(archive.read_bytes()).hexdigest() if checksum_ok else '0'*64
            curl=base/'curl'
            curl.write_text('#!/usr/bin/env python3\nimport os,sys,shutil\na=sys.argv[1:]; dst=a[a.index("-o")+1]; url=next(x for x in a if x.startswith("https://"))\nif url.endswith(".sha256"):\n open(dst,"w").write(os.environ["FIXTURE_HASH"]+"  pvnetwork-panel-v1.0.41.tar.gz\\n")\nelse: shutil.copyfile(os.environ["FIXTURE_ARCHIVE"],dst)\n')
            curl.chmod(0o755)
            marker=base/'invoked'
            env={**os.environ,'PATH':str(base)+os.pathsep+os.environ['PATH'],
                 'PVNETWORK_REF':'v1.0.41','FIXTURE_ARCHIVE':str(archive),'FIXTURE_HASH':digest,'MARKER':str(marker)}
            args=['bash',str(ROOT/'install.sh')]
            if os.geteuid()!=0:
                if not shutil.which('sudo'):self.skipTest('root bootstrap fixture requires root or noninteractive sudo')
                # Only this synthetic archive/curl fixture runs as root. Never
                # run the actual product installation on the CI runner host.
                values={k:env[k] for k in ['PATH','PVNETWORK_REF','FIXTURE_ARCHIVE','FIXTURE_HASH','MARKER']}
                args=['sudo','-n','env',*(k+'='+v for k,v in values.items()),*args]
            result=subprocess.run(args,env=env,capture_output=True,text=True,timeout=15)
            return result.returncode, marker.exists(), result.stdout+result.stderr

    def test_corrupt_checksum_never_executes_installer(self):
        code,invoked,output=self.run_bootstrap(checksum_ok=False)
        self.assertNotEqual(code,0,output);self.assertFalse(invoked)

    def test_wrong_release_version_never_executes_installer(self):
        code,invoked,output=self.run_bootstrap(version='1.0.40')
        self.assertNotEqual(code,0,output);self.assertFalse(invoked)

    def test_link_archive_never_executes_installer(self):
        code,invoked,output=self.run_bootstrap(extra=('release/link',tarfile.SYMTYPE,'/tmp'))
        self.assertNotEqual(code,0,output);self.assertFalse(invoked)

    def test_verified_release_executes_installer(self):
        code,invoked,output=self.run_bootstrap()
        self.assertEqual(code,0,output);self.assertTrue(invoked)


class FreshHostPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('pvnetwork_install',ROOT/'scripts/pvnetwork_install.py')
        cls.install=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.install)

    def test_unsupported_os_refused(self):
        with self.assertRaises(ValueError):self.install.validate_host('ubuntu','20.04','x86_64',2*1024**3,10*1024**3)

    def test_unsupported_architecture_refused(self):
        with self.assertRaises(ValueError):self.install.validate_host('ubuntu','24.04','i686',2*1024**3,10*1024**3)

    def test_insufficient_resources_refused(self):
        with self.assertRaises(ValueError):self.install.validate_host('debian','12','x86_64',256*1024**2,10*1024**3)
        with self.assertRaises(ValueError):self.install.validate_host('debian','12','x86_64',2*1024**3,128*1024**2)

    def test_supported_hosts_pass(self):
        for system,version in [('ubuntu','22.04'),('ubuntu','24.04'),('debian','12')]:
            self.install.validate_host(system,version,'x86_64',2*1024**3,10*1024**3)

    def test_existing_install_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'main.py').write_text('preserved')
            with self.assertRaises(ValueError):self.install.check_existing_install(root)
            self.assertEqual((root/'main.py').read_text(),'preserved')

    def test_occupied_loopback_port_refused(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            with self.assertRaises(ValueError):self.install.check_port(listener.getsockname()[1])

    def test_config_injection_refused(self):
        for value in ['panel\nJWT_SECRET_KEY=bad','../panel','panel;echo']:
            with self.assertRaises(ValueError):self.install.validate_path(value)

    def test_https_is_not_announced_before_verification(self):
        with self.assertRaises(ValueError):self.install.access_url('vpn.example.com','panel',18443,tls_verified=False)
        self.assertEqual(self.install.access_url(None,'panel',18443,tls_verified=False),'http://127.0.0.1:18443/panel/')

    def test_pre_tls_domain_proxy_does_not_expose_login_over_http(self):
        conf=self.install.proxy_config(19000,'panel',18443,'vpn.example.com',tls=False)
        self.assertIn('return 503',conf)
        self.assertNotIn('proxy_pass',conf)

    def test_interrupted_nonterminal_install_is_recoverable(self):
        for phase in ['staging','build','database','activation','health','timers','failed']:
            self.assertTrue(self.install.recoverable_phase(phase))
        self.assertFalse(self.install.recoverable_phase('complete'))
        self.assertFalse(self.install.recoverable_phase('unrecognized'))
