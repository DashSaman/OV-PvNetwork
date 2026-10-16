"""Opt-in native fresh/repeat acceptance on a disposable Linux Docker runner.

Never targets an existing container, publishes a host port or imports host state.
Run explicitly: python tests/native_installer_systemd.py ubuntu2404
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
BASES = {
    'ubuntu2204': 'ubuntu@sha256:08ea48a03a3e78ebc7cd526e6a275053223aadd88bfc09cc49b06d5281525fde',
    'ubuntu2404': 'ubuntu@sha256:f610ab94648195aa356059f5b41d6085c9d4d903c072430cdd1af7bdb646106b',
    'debian12': 'debian@sha256:bc49dc1918ee1a47a93e65b5e4676e8680fb754b133197b92ca52bfe6731d5f0',
}


def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, timeout=2400, **kwargs)


def inside(expected):
    archive = Path('/input/source.tar.gz')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
    source = Path('/root/pvnetwork-source')
    source.mkdir(exist_ok=False)
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert member.isfile() or member.isdir()
            if member.isfile():
                data = bundle.extractfile(member).read()
                if data.startswith(b'#!'):
                    assert b'\r' not in data, member.name
        bundle.extractall(source)
    version = (source / 'VERSION').read_text().strip()
    environment = {**os.environ, 'PVNETWORK_RELEASE_VERSION': version,
                   'PVNETWORK_SOURCE_SHA256': expected, 'DEBIAN_FRONTEND': 'noninteractive'}
    installed = subprocess.run(['bash', str(source / 'install-local.sh'), '--non-interactive'],
                               env=environment, capture_output=True, text=True, timeout=2400)
    # Do not upload raw logs or generated credentials/PKI to a public CI artifact.
    diagnostic = Path('/root/pvnetwork-native-install.log')
    diagnostic.write_text(installed.stdout + '\n' + installed.stderr)
    diagnostic.chmod(0o600)
    journal_path = Path('/etc/pvnetwork-panel/install-transaction.json')
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else {}
    if installed.returncode:
        error = Path('/etc/pvnetwork-panel/last-install-error.log')
        # Dependency errors are useful, but suppress any line resembling a secret.
        lines = error.read_text(errors='replace').splitlines() if error.exists() else installed.stderr.splitlines()
        safe = [line for line in lines if not re.search(r'secret|password|token|credential|PRIVATE KEY|CERTIFICATE|://[^/\s]+@', line, re.I)]
        safe = [re.sub(r'(https?://[^\s?]+)\?[^\s]+', r'\1?[query omitted]', line) for line in safe]
        print(json.dumps({'install_exit': installed.returncode, 'phase': journal.get('phase'),
                          'diagnostic_tail': safe[-30:]}), flush=True)
        raise SystemExit(installed.returncode)
    app = Path('/opt/pvnetwork-panel')
    assert app.is_symlink() and journal['phase'] == 'complete' and journal['version'] == version
    assert journal['source_sha256'] == expected
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    origin = 'http://127.0.0.1:18443'
    for route in ['/healthz', '/panel/']:
        with opener.open(origin + route, timeout=10) as response:
            assert response.status == 200
            if route == '/healthz':
                assert json.load(response)['version'] == version
            else:
                html = response.read().decode()
                assets = re.findall(r'(?:src|href)=["\']([^"\']*/assets/[^"\']+)["\']', html)
                assert assets
                for reference in assets:
                    with opener.open(urljoin(origin + '/panel/', reference), timeout=10) as remote:
                        assert hashlib.sha256(remote.read()).digest() == hashlib.sha256((app / 'frontend/dist/assets' / reference.rsplit('/', 1)[-1]).read_bytes()).digest()
    for path in [app / '.env', Path('/etc/pvnetwork-panel/initial-credentials.txt')]:
        assert path.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(app / 'data/pvnetwork-panel.db') as database:
        assert database.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert database.execute('SELECT version_num FROM alembic_version').fetchone()[0] == 'i1b2c3d4e5f6'
        assert database.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='node_tls_bindings'").fetchone()[0] == 1
    protected = [app / '.env', app / 'data/pvnetwork-panel.db']
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    pids = run(['systemctl', 'show', 'pvnetwork-panel.service', 'nginx.service', '-p', 'MainPID'], capture_output=True, text=True).stdout
    repeated = run(['bash', source / 'install-local.sh', '--non-interactive'], env=environment, capture_output=True, text=True)
    assert 'already installed' in repeated.stdout
    assert before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    assert pids == run(['systemctl', 'show', 'pvnetwork-panel.service', 'nginx.service', '-p', 'MainPID'], capture_output=True, text=True).stdout
    for command in ['version', 'status', 'doctor']:
        result = run(['/usr/local/sbin/pvnetwork', command, '--json'], capture_output=True, text=True)
        assert isinstance(json.loads(result.stdout), dict)
    print(json.dumps({'native_fresh': 'PASS', 'repeat_env_DB_PIDs_preserved': 'PASS',
                      'systemd_proxy_UI_assets_SQLite_permissions': 'PASS', 'installed_CLI': 'PASS',
                      'version': version, 'source_sha256': expected,
                      'limits': 'Container Setup Mode; public ACME and external VPS networking not tested'}), flush=True)


def host(system):
    if sys.platform != 'linux' or not shutil.which('docker'):
        raise SystemExit('An explicitly disposable Linux Docker runner is required')
    name = 'pvnetwork-fresh-' + system + '-' + os.urandom(6).hex()
    image = 'pvnetwork-native-test:' + system + '-' + os.urandom(6).hex()
    with tempfile.TemporaryDirectory(prefix='pvnetwork-native-ci-') as temporary:
        folder = Path(temporary)
        raw = subprocess.check_output(['git', '-c', 'core.autocrlf=true', 'archive', '--format=tar', 'HEAD'], cwd=ROOT)
        archive = folder / 'source.tar.gz'
        with archive.open('wb') as target:
            with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0) as zipped:
                zipped.write(raw)
        expected = hashlib.sha256(archive.read_bytes()).hexdigest()
        shutil.copyfile(__file__, folder / 'runner.py')
        context = folder / 'image'
        context.mkdir()
        (context / 'Dockerfile').write_text('FROM ' + BASES[system] + '\nENV container=docker\nENV DEBIAN_FRONTEND=noninteractive\nRUN apt-get update --error-on=any && apt-get install -y --no-install-recommends systemd systemd-sysv dbus python3 ca-certificates curl && rm -rf /var/lib/apt/lists/*\nSTOPSIGNAL SIGRTMIN+3\nENTRYPOINT ["/sbin/init"]\n')
        created = False
        try:
            run(['docker', 'build', '-t', image, context])
            run(['docker', 'run', '-d', '--name', name, '--label', 'pvnetwork.test.owner=native-ci',
                 '--privileged', '--cgroupns=private', '--tmpfs', '/run', '--tmpfs', '/run/lock',
                 '--tmpfs', '/tmp', '--stop-signal', 'SIGRTMIN+3', '-v', str(folder) + ':/input:ro', image])
            created = True
            for _ in range(60):
                state = subprocess.run(['docker', 'exec', name, 'systemctl', 'is-system-running'], capture_output=True, text=True)
                if state.stdout.strip() in {'running', 'degraded'}:
                    break
                time.sleep(.5)
            else:
                raise RuntimeError('Disposable systemd guest failed to boot')
            run(['docker', 'exec', name, 'python3', '/input/runner.py', '--inside', expected])
        finally:
            if created:
                subprocess.run(['docker', 'rm', '-f', name], check=False)
            subprocess.run(['docker', 'image', 'rm', image], check=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('system', nargs='?', choices=BASES)
    parser.add_argument('--inside', metavar='SHA256')
    arguments = parser.parse_args()
    if arguments.inside:
        if not re.fullmatch('[a-f0-9]{64}', arguments.inside):
            parser.error('A fixed archive SHA256 is required')
        inside(arguments.inside)
    elif arguments.system:
        host(arguments.system)
    else:
        parser.error('Select the disposable guest distribution')
