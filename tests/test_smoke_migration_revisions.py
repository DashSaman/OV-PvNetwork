import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")


@unittest.skipUnless(BASH, "Bash is required to execute the smoke stage")
class SmokeMigrationRevisionTests(unittest.TestCase):
    def run_stage(self, heads, current):
        source = (ROOT / "scripts/pvnetwork-panel-smoke-test").read_text(encoding="utf-8")
        stage = source.split('echo "PVNETWORK_SMOKE_STAGE=ALEMBIC"\n', 1)[1]
        stage = stage.split('echo "PVNETWORK_SMOKE_STAGE=DATABASE"', 1)[0]
        with tempfile.TemporaryDirectory(prefix="pvnetwork-smoke-") as directory:
            root = Path(directory)
            (root / "backend").mkdir()
            executable = root / ".venv/bin/alembic"
            executable.parent.mkdir(parents=True)
            executable.write_text(
                '#!/usr/bin/env bash\n'
                'case "${!#}" in\n'
                'heads) printf "%s" "$TEST_ALEMBIC_HEADS" ;;\n'
                'current) printf "%s" "$TEST_ALEMBIC_CURRENT" ;;\n'
                '*) exit 99 ;;\n'
                'esac\n',
                encoding="utf-8",
            )
            executable.chmod(0o755)
            environment = dict(os.environ, TEST_ALEMBIC_HEADS=heads, TEST_ALEMBIC_CURRENT=current)
            return subprocess.run(
                [BASH, "-c", "set -Eeuo pipefail\n" + stage],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                timeout=10,
            )

    def test_accepts_the_shipped_alphanumeric_revision(self):
        result = self.run_stage("h0a1b2c3d4e5 (head)\n", "h0a1b2c3d4e5 (head)\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ALEMBIC_EXPECTED_HEAD=h0a1b2c3d4e5", result.stdout)
        self.assertIn("ALEMBIC_CURRENT_HEAD=h0a1b2c3d4e5", result.stdout)

    def test_accepts_a_hexadecimal_revision(self):
        result = self.run_stage("e7f8a9b0c1d2 (head)\n", "e7f8a9b0c1d2 (head)\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_an_empty_head(self):
        result = self.run_stage("", "h0a1b2c3d4e5 (head)\n")
        self.assertEqual(result.returncode, 31, result.stdout + result.stderr)
        self.assertIn("ALEMBIC_HEAD_COUNT_INVALID=0", result.stdout)

    def test_rejects_multiple_heads(self):
        result = self.run_stage("h0a1b2c3d4e5 (head)\ne7f8a9b0c1d2 (head)\n", "h0a1b2c3d4e5 (head)\n")
        self.assertEqual(result.returncode, 31, result.stdout + result.stderr)
        self.assertIn("ALEMBIC_HEAD_COUNT_INVALID=2", result.stdout)

    def test_rejects_a_missing_current_revision(self):
        result = self.run_stage("h0a1b2c3d4e5 (head)\n", "")
        self.assertEqual(result.returncode, 32, result.stdout + result.stderr)
        self.assertIn("ALEMBIC_CURRENT_NOT_FOUND", result.stdout)

    def test_rejects_a_different_current_revision(self):
        result = self.run_stage("h0a1b2c3d4e5 (head)\n", "g9a0b1c2d3e4\n")
        self.assertEqual(result.returncode, 33, result.stdout + result.stderr)
        self.assertIn("ALEMBIC_NOT_AT_HEAD", result.stdout)
