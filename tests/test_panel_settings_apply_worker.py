import hashlib
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("MAIN_ADMIN_AUTH_GENERATION", "ci-generation")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

from backend import panel_runtime_settings as runtime

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pvnetwork-panel-settings-apply.py"


def load_worker(testcase):
    testcase.assertTrue(SCRIPT.exists(), "panel settings apply worker must exist")
    spec = importlib.util.spec_from_file_location("panel_settings_apply_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WorkerHarness:
    def __init__(self, testcase):
        self.testcase = testcase
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.app = self.root / "app"
        self.staging = self.root / "stage"
        self.backups = self.root / "backups"
        self.jobs = self.root / "jobs"
        self.transition = self.root / "transition.json"
        (self.app / "frontend/dist").mkdir(parents=True)
        self.staging.mkdir(parents=True)
        self.live_env = self.app / ".env"
        self.live_env.write_text(
            "ADMIN_USERNAME=old-admin\n"
            "ADMIN_PASSWORD_HASH=oldhash\n"
            "MAIN_ADMIN_AUTH_GENERATION=oldgen\n"
            "URLPATH=oldpath\nVITE_URLPATH=oldpath\nPORT=19001\n",
            encoding="utf-8",
        )
        (self.app / "frontend/dist/version.txt").write_text("old", encoding="utf-8")
        (self.staging / "candidate.env").write_text(
            "ADMIN_USERNAME=new-admin\n"
            "ADMIN_PASSWORD_HASH=newhash\n"
            "MAIN_ADMIN_AUTH_GENERATION=newgen\n"
            "URLPATH=newpath\nVITE_URLPATH=newpath\nPORT=19001\n",
            encoding="utf-8",
        )
        self.change_id = "change-1"

    def close(self):
        self.tmp.cleanup()

    def snapshot_live(self):
        return (
            self.live_env.read_bytes(),
            sorted(
                (p.relative_to(self.app / "frontend/dist").as_posix(), p.read_bytes())
                for p in (self.app / "frontend/dist").rglob("*")
                if p.is_file()
            ),
        )

    def prepare(self, worker):
        worker.APP_DIR = self.app
        worker.BACKUP_ROOT = self.backups
        runtime.JOB_DIR = self.jobs
        runtime.TRANSITION_FILE = self.transition
        runtime.write_job_state(
            self.change_id,
            {
                "status": "queued",
                "old_path": "oldpath",
                "new_path": "newpath",
                "expected_env_sha256": sha256(self.live_env),
                "changed_fields": ["username", "password", "path"],
            },
        )

    def fake_build(self, worker):
        dist = self.staging / "dist"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "version.txt").write_text("new", encoding="utf-8")
        return dist


class PanelSettingsWorkerTests(unittest.TestCase):
    def setUp(self):
        self.worker = load_worker(self)
        self.harness = WorkerHarness(self)
        self.harness.prepare(self.worker)

    def tearDown(self):
        self.harness.close()

    def test_frontend_paths_are_injectable(self):
        vite = (ROOT / "frontend/vite.config.js").read_text(encoding="utf-8")
        app = (ROOT / "backend/app.py").read_text(encoding="utf-8")
        self.assertIn("PVNETWORK_BUILD_OUTDIR", vite)
        self.assertIn("PVNETWORK_FRONTEND_DIST", app)

    def test_build_failure_never_mutates_live_files(self):
        before = self.harness.snapshot_live()
        with patch.object(self.worker, "build_frontend", side_effect=RuntimeError("build failed")), patch.object(self.worker, "restart_service") as restart:
            result = self.worker.run_change(self.harness.change_id, self.harness.staging, 9)
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual(self.harness.snapshot_live(), before)
        restart.assert_not_called()

    def test_stale_live_env_hash_aborts_before_build(self):
        runtime.write_job_state(
            self.harness.change_id,
            {
                "status": "queued",
                "old_path": "oldpath",
                "new_path": "newpath",
                "expected_env_sha256": "0" * 64,
                "changed_fields": ["path"],
            },
        )
        before = self.harness.snapshot_live()
        with patch.object(self.worker, "build_frontend") as build, patch.object(self.worker, "restart_service") as restart:
            result = self.worker.run_change(self.harness.change_id, self.harness.staging, 9)
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual(self.harness.snapshot_live(), before)
        build.assert_not_called()
        restart.assert_not_called()

    def test_post_switch_failure_restores_exact_env_and_dist(self):
        before = self.harness.snapshot_live()
        restarts = []
        with patch.object(self.worker, "build_frontend", side_effect=lambda *_: self.harness.fake_build(self.worker)), patch.object(self.worker, "start_candidate", return_value=object()), patch.object(self.worker, "verify_candidate", return_value=True), patch.object(self.worker, "stop_candidate"), patch.object(self.worker, "verify_canonical", return_value=False), patch.object(self.worker, "restart_service", side_effect=lambda name: restarts.append(name)):
            result = self.worker.run_change(self.harness.change_id, self.harness.staging, 9)
        self.assertEqual(result["status"], "rolled_back")
        self.assertEqual(self.harness.snapshot_live(), before)
        self.assertEqual(restarts, ["pvnetwork-panel.service", "pvnetwork-panel.service"])

    def test_success_switches_once_and_writes_five_minute_transition(self):
        restarts = []
        with patch.object(self.worker, "build_frontend", side_effect=lambda *_: self.harness.fake_build(self.worker)), patch.object(self.worker, "start_candidate", return_value=object()), patch.object(self.worker, "verify_candidate", return_value=True), patch.object(self.worker, "stop_candidate"), patch.object(self.worker, "verify_canonical", return_value=True), patch.object(self.worker, "restart_service", side_effect=lambda name: restarts.append(name)), patch.object(self.worker.time, "time", return_value=1000):
            result = self.worker.run_change(self.harness.change_id, self.harness.staging, 9)
        self.assertEqual(result["status"], "complete")
        self.assertIn("ADMIN_USERNAME=new-admin", self.harness.live_env.read_text(encoding="utf-8"))
        self.assertEqual((self.harness.app / "frontend/dist/version.txt").read_text(encoding="utf-8"), "new")
        self.assertEqual(restarts, ["pvnetwork-panel.service"])
        transition = runtime.load_transition_state()
        self.assertEqual(transition["old_path"], "oldpath")
        self.assertEqual(transition["new_path"], "newpath")
        self.assertEqual(transition["redirect_expires_at"], 1300)

    def test_restart_service_rejects_every_non_panel_service(self):
        for name in ["openvpn-server@server.service", "ov-node.service", "nginx.service", "pvnetwork-firewall-hardening.service"]:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                self.worker.restart_service(name)

    def test_runtime_installer_installs_worker(self):
        source = (ROOT / "scripts/install-runtime-tools.sh").read_text(encoding="utf-8")
        self.assertIn("pvnetwork-panel-settings-apply", source)


if __name__ == "__main__":
    unittest.main()


class PanelSettingsWorkerCliTests(unittest.TestCase):
    def test_worker_help_runs_outside_app_cwd(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PVNETWORK_APP_DIR"] = str(ROOT)
            result = subprocess.run(
                [str(SCRIPT), "--help"],
                cwd=tmp,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("--change-id", result.stdout)
