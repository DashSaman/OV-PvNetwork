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

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "backend/panel_runtime_settings.py"


def load_runtime(testcase):
    testcase.assertTrue(MODULE_PATH.exists(), "panel runtime settings module must exist")
    spec = importlib.util.spec_from_file_location("panel_runtime_settings_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PanelRuntimeValidationTests(unittest.TestCase):
    def test_reserved_and_case_colliding_paths_are_rejected(self):
        runtime = load_runtime(self)
        for value in ["api", "API", "healthz", "assets", "sub", "SUB"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime.validate_panel_path(value, "sub")

    def test_valid_path_and_username_are_normalized(self):
        runtime = load_runtime(self)
        self.assertEqual(runtime.validate_panel_path("Panel_12-x", "sub"), "Panel_12-x")
        self.assertEqual(runtime.validate_admin_username("  owner name  ", {"reseller"}), "owner name")
    def test_username_collision_and_controls_are_rejected(self):
        runtime = load_runtime(self)
        for value in ["ab", "x" * 65, "bad\nname", "Reseller"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime.validate_admin_username(value, {"reseller"})

    def test_candidate_env_changes_only_requested_fields(self):
        runtime = load_runtime(self)
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text(
                "ADMIN_USERNAME=old\n"
                "ADMIN_PASSWORD_HASH=oldhash\n"
                "MAIN_ADMIN_AUTH_GENERATION=oldgen\n"
                "URLPATH=oldpath\nVITE_URLPATH=oldpath\nPORT=19001\n",
                encoding="utf-8",
            )
            text = runtime.build_candidate_env(env, None, None, "newpath", None)
            self.assertIn("ADMIN_USERNAME=old", text)
            self.assertIn("ADMIN_PASSWORD_HASH=oldhash", text)
            self.assertIn("MAIN_ADMIN_AUTH_GENERATION=oldgen", text)
            self.assertIn("URLPATH=newpath", text)
            self.assertIn("VITE_URLPATH=newpath", text)
            self.assertIn("PORT=19001", text)

    def test_candidate_env_rotates_supplied_credentials_generation(self):
        runtime = load_runtime(self)
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("ADMIN_USERNAME=old\nADMIN_PASSWORD_HASH=oldhash\nMAIN_ADMIN_AUTH_GENERATION=oldgen\nURLPATH=old\nVITE_URLPATH=old\n", encoding="utf-8")
            text = runtime.build_candidate_env(env, "new-owner", "newhash", None, "newgen")
            self.assertIn("ADMIN_USERNAME=new-owner", text)
            self.assertIn("ADMIN_PASSWORD_HASH=newhash", text)
            self.assertIn("MAIN_ADMIN_AUTH_GENERATION=newgen", text)


class PanelRuntimeStateTests(unittest.TestCase):
    def test_job_state_rejects_secret_keys_recursively(self):
        runtime = load_runtime(self)
        with tempfile.TemporaryDirectory() as tmp, patch.object(runtime, "JOB_DIR", Path(tmp)):
            for payload in [
                {"status": "queued", "new_password": "secret"},
                {"status": "queued", "nested": {"jwt": "secret"}},
                {"status": "queued", "items": [{"token": "secret"}]},
            ]:
                with self.subTest(payload=payload), self.assertRaises(ValueError):
                    runtime.write_job_state("abc", payload)

    def test_job_state_roundtrip_is_private_and_atomic(self):
        runtime = load_runtime(self)
        with tempfile.TemporaryDirectory() as tmp, patch.object(runtime, "JOB_DIR", Path(tmp)):
            runtime.write_job_state("abc-123", {"status": "queued", "new_path": "next"})
            path = Path(tmp) / "abc-123.json"
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(runtime.read_job_state("abc-123")["new_path"], "next")

    def test_transition_state_roundtrip(self):
        runtime = load_runtime(self)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "transition.json"
            with patch.object(runtime, "TRANSITION_FILE", path):
                runtime.write_transition_state({"old_path": "old", "new_path": "new", "redirect_expires_at": 123})
                self.assertEqual(runtime.load_transition_state()["new_path"], "new")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class PanelRuntimeTokenLockTests(unittest.TestCase):
    def test_change_status_token_rejects_tamper_wrong_change_and_expiry(self):
        runtime = load_runtime(self)
        token = runtime.mint_change_status_token("change-a", ttl_seconds=60)
        self.assertIsNone(runtime.verify_change_status_token(token, "change-a"))
        with self.assertRaises(ValueError):
            runtime.verify_change_status_token(token, "change-b")
        with self.assertRaises(ValueError):
            runtime.verify_change_status_token(token + "x", "change-a")
        expired = runtime.mint_change_status_token("change-a", ttl_seconds=-1)
        with self.assertRaises(ValueError):
            runtime.verify_change_status_token(expired, "change-a")

    def test_apply_lock_is_nonblocking(self):
        runtime = load_runtime(self)
        with tempfile.TemporaryDirectory() as tmp, patch.object(runtime, "LOCK_FILE", Path(tmp) / "apply.lock"):
            fd = runtime.acquire_apply_lock()
            try:
                with self.assertRaises(runtime.ApplyBusy):
                    runtime.acquire_apply_lock()
            finally:
                os.close(fd)

    def test_spawn_helper_passes_only_non_secret_identifiers(self):
        runtime = load_runtime(self)
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "jobs"
            staging = Path(tmp) / "stage"
            staging.mkdir()
            with patch.object(runtime, "JOB_DIR", job_dir), patch.object(runtime, "APPLY_HELPER", "/usr/local/sbin/pvnetwork-panel-settings-apply"), patch("subprocess.Popen") as popen:
                popen.return_value.pid = 4242
                pid = runtime.spawn_apply_helper("change-1", staging, 9)
            self.assertEqual(pid, 4242)
            args = popen.call_args.args[0]
            self.assertEqual(args, [
                "/usr/local/sbin/pvnetwork-panel-settings-apply",
                "--change-id", "change-1",
                "--staging-dir", str(staging),
                "--lock-fd", "9",
            ])
            self.assertEqual(popen.call_args.kwargs["pass_fds"], (9,))
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            joined = " ".join(args).lower()
            for word in ["password", "jwt", "token", "secret", "env="]:
                self.assertNotIn(word, joined)


if __name__ == "__main__":
    unittest.main()
