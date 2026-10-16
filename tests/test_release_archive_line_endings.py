"""Exercise Git's export conversion, rather than normalized QA source copies."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = b'#!/bin/sh\nset -eu\nprintf "PVNETWORK_ARCHIVE_LF=PASS\\n"\n'
BINARY = b'\x89PNG\r\n\x1a\n\0private-demo-binary\r\n\xff'


class ReleaseArchiveLineEndingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='pvnetwork-git-export-')
        cls.repo = Path(cls.temporary.name)
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=cls.repo, stderr=subprocess.PIPE)
        cls.git = staticmethod(git)
        git('init', '-q')
        attributes = ROOT / '.gitattributes'
        if attributes.exists():
            (cls.repo / '.gitattributes').write_bytes(attributes.read_bytes())
        (cls.repo / 'entry.sh').write_bytes(SHELL)
        (cls.repo / 'pvnetwork').write_bytes(SHELL)
        (cls.repo / 'demo.png').write_bytes(BINARY)
        (cls.repo / 'guide.md').write_text('PVNetwork Demo / فارسی\n', encoding='utf-8', newline='\n')
        git('-c', 'core.autocrlf=false', 'add', '.')
        git('update-index', '--chmod=+x', 'entry.sh')
        git('update-index', '--chmod=+x', 'pvnetwork')
        git('-c', 'user.name=PVNetwork Demo', '-c', 'user.email=demo@example.invalid', 'commit', '-qm', 'Demo export fixture')
        cls.archive = git('-c', 'core.autocrlf=true', 'archive', '--format=tar', 'HEAD')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_windows_style_git_exports_exact_executable_lf_bytes(self):
        with tarfile.open(fileobj=io.BytesIO(self.archive)) as archive:
            for name in ['entry.sh', 'pvnetwork']:
                script = archive.extractfile(name).read()
                self.assertEqual(script, SHELL, 'Git export converted executable source to CRLF')
                self.assertEqual(archive.getmember(name).mode & 0o111, 0o111)

    def test_binary_asset_hash_is_unchanged(self):
        with tarfile.open(fileobj=io.BytesIO(self.archive)) as archive:
            self.assertEqual(hashlib.sha256(archive.extractfile('demo.png').read()).digest(), hashlib.sha256(BINARY).digest())

    def test_text_export_is_platform_independent(self):
        other = self.git('-c', 'core.autocrlf=false', 'archive', '--format=tar', 'HEAD')
        self.assertEqual(self.archive, other)

    @unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Actual Bash execution runs in Linux CI')
    def test_exported_entry_point_executes_in_bash(self):
        with tarfile.open(fileobj=io.BytesIO(self.archive)) as archive:
            script = archive.extractfile('entry.sh').read()
        result = subprocess.run(['bash'], input=script, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout, b'PVNETWORK_ARCHIVE_LF=PASS\n')


if __name__ == '__main__':
    unittest.main()
