"""The actual issuance command must persist safe automatic certificate activation."""
import ast
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def issuance_arguments():
    # Read the actual installer command without running a host installation or
    # substituting a different command builder just for the test.
    tree = ast.parse((ROOT / 'scripts/pvnetwork_install.py').read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'command'
             and node.args and isinstance(node.args[0], ast.List)
             and node.args[0].elts and isinstance(node.args[0].elts[0], ast.Constant)
             and node.args[0].elts[0].value == 'certbot']
    if len(calls) != 1:
        raise AssertionError('Expected exactly one fresh-install certificate issuance command')
    expression = ast.Expression(calls[0].args[0])
    return eval(compile(expression, '<installer issuance>', 'eval'), {'__builtins__': {}},
                {'acme': Path('/private-synthetic-acme'),
                 'args': SimpleNamespace(domain='panel.example.invalid', email='qa@example.invalid')})


class InstallerTlsRenewalTests(unittest.TestCase):
    def deploy_hook(self):
        arguments = issuance_arguments()
        self.assertIn('--deploy-hook', arguments,
                      'Automatic webroot renewal must activate the new Nginx certificate')
        self.assertEqual(arguments.count('--deploy-hook'), 1)
        self.assertNotIn('--force-renewal', arguments)
        return arguments[arguments.index('--deploy-hook') + 1]

    def test_webroot_issuance_persists_successful_renewal_hook(self):
        arguments = issuance_arguments()
        self.assertIn('--webroot', arguments)
        hook = self.deploy_hook()
        self.assertNotIn('restart', hook)
        self.assertNotIn('stop', hook)

    @unittest.skipUnless(os.name == 'posix' and shutil.which('sh'), 'requires POSIX shell')
    def test_hook_reloads_only_after_successful_syntax_check(self):
        self.run_hook(0, ['nginx -t', 'systemctl reload nginx.service'])

    @unittest.skipUnless(os.name == 'posix' and shutil.which('sh'), 'requires POSIX shell')
    def test_invalid_configuration_never_reloads_or_restarts_service(self):
        self.run_hook(1, ['nginx -t'])

    def run_hook(self, nginx_exit, expected):
        hook = self.deploy_hook()
        with tempfile.TemporaryDirectory(prefix='pvnetwork-tls-hook-') as temporary:
            folder = Path(temporary)
            log = folder / 'calls'
            for name in ['nginx', 'systemctl']:
                executable = folder / name
                executable.write_text('#!/bin/sh\nprintf "%s\\n" "' + name + ' $*" >> "$CALLS"\n'
                                      + ('exit "$NGINX_EXIT"\n' if name == 'nginx' else 'exit 0\n'))
                executable.chmod(0o700)
            result = subprocess.run(['/bin/sh', '-c', hook], env={**os.environ, 'PATH': str(folder),
                                    'CALLS': str(log), 'NGINX_EXIT': str(nginx_exit)},
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, nginx_exit, result.stderr)
            self.assertEqual(log.read_text().splitlines(), expected)

    @unittest.skipUnless(os.name == 'posix' and shutil.which('nginx') and shutil.which('openssl'),
                         'requires isolated Linux Nginx/OpenSSL fixture')
    def test_real_nginx_serves_new_certificate_only_after_safe_reload(self):
        hook = self.deploy_hook()
        nginx = shutil.which('nginx')
        with tempfile.TemporaryDirectory(prefix='pvnetwork-tls-real-') as temporary:
            folder = Path(temporary)
            for number in [1, 2]:
                subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                                '-days', '1', '-subj', '/CN=panel.example.invalid', '-set_serial', str(number),
                                '-keyout', str(folder / f'key{number}'), '-out', str(folder / f'cert{number}')],
                               check=True, capture_output=True, timeout=20)
            cert = folder / 'cert.pem'
            key = folder / 'key.pem'
            shutil.copyfile(folder / 'cert1', cert)
            shutil.copyfile(folder / 'key1', key)
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            conf = folder / 'nginx.conf'
            configuration = ('pid ' + str(folder / 'nginx.pid') + ';\nerror_log ' + str(folder / 'error.log')
                             + ';\nevents {}\nhttp { access_log off; server { listen 127.0.0.1:' + str(port)
                             + ' ssl; ssl_certificate ' + str(cert) + '; ssl_certificate_key ' + str(key)
                             + '; location / { return 200 "synthetic TLS fixture"; } } }\n')
            conf.write_text(configuration)
            wrappers = folder / 'bin'
            wrappers.mkdir()
            # Keep the actual hook unchanged. Only service-command boundaries
            # target this private master/config instead of any host service.
            (wrappers / 'nginx').write_text('#!/bin/sh\nexec "' + nginx + '" "$@" -p "' + str(folder)
                                          + '" -c "' + str(conf) + '"\n')
            (wrappers / 'systemctl').write_text('#!' + sys.executable + '\nimport os,signal,sys\n'
                + 'assert sys.argv[1:] == ["reload","nginx.service"]\n'
                + 'os.kill(int(open(' + repr(str(folder / 'nginx.pid')) + ').read()),signal.SIGHUP)\n')
            for path in wrappers.iterdir():
                path.chmod(0o700)
            process = subprocess.Popen([nginx, '-p', str(folder), '-c', str(conf), '-g', 'daemon off;'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # Synthetic certificates; loopback fixture only.

            def served_certificate():
                with socket.create_connection(('127.0.0.1', port), timeout=1) as raw:
                    with context.wrap_socket(raw, server_hostname='panel.example.invalid') as connection:
                        return connection.getpeercert(binary_form=True)

            def wait_for(expected):
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    self.assertIsNone(process.poll(), 'Private Nginx master exited')
                    try:
                        if served_certificate() == expected:
                            return
                    except (OSError, ssl.SSLError):
                        pass
                    time.sleep(.05)
                self.fail('Private Nginx did not serve the expected synthetic certificate')

            try:
                first = ssl.PEM_cert_to_DER_cert((folder / 'cert1').read_text())
                second = ssl.PEM_cert_to_DER_cert((folder / 'cert2').read_text())
                wait_for(first)
                pid = (folder / 'nginx.pid').read_text()
                shutil.copyfile(folder / 'cert2', cert)
                shutil.copyfile(folder / 'key2', key)
                self.assertEqual(served_certificate(), first, 'File replacement alone must reproduce stale TLS')
                env = {**os.environ, 'PATH': str(wrappers)}
                conf.write_text(configuration + 'pvnetwork_invalid_fixture_directive;\n')
                failed = subprocess.run(['/bin/sh', '-c', hook], env=env,
                                        capture_output=True, text=True, timeout=5)
                self.assertNotEqual(failed.returncode, 0)
                self.assertEqual(served_certificate(), first)
                conf.write_text(configuration)
                passed = subprocess.run(['/bin/sh', '-c', hook], env=env,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(passed.returncode, 0, passed.stderr)
                wait_for(second)
                self.assertEqual((folder / 'nginx.pid').read_text(), pid)
                self.assertEqual(process.pid, int(pid))
                self.assertIsNone(process.poll())
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
