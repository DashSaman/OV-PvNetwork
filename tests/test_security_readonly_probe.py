import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pvnetwork-security-readonly-probe.py"


class FakeResponse:
    def __init__(self, status, headers=None):
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args, **_kwargs):
        return b""


class ReadonlyProbeTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SCRIPT.is_file(), "read-only security probe script must exist")
        spec = importlib.util.spec_from_file_location("pvnetwork_security_probe", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_probe_checks_expected_status_headers_and_untrusted_cors(self):
        module = self.module()
        security_headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=()",
        }
        statuses = {
            "/healthz": (200, security_headers),
            "/openapi.json": (404, {}),
            "/redoc": (404, {}),
            "/api/users/": (401, {}),
            "/api/security/": (401, {}),
        }
        seen = []

        def opener(request, timeout=0):
            from urllib.parse import urlsplit
            seen.append((request.get_method(), urlsplit(request.full_url).path, dict(request.header_items())))
            status, headers = statuses[urlsplit(request.full_url).path]
            return FakeResponse(status, headers)

        lines = module.run_probe("https://panel.example", opener=opener)
        self.assertTrue(lines[-1].endswith("=PASS"))
        self.assertEqual({path for _, path, _ in seen}, set(statuses))
        self.assertTrue(all(method == "GET" for method, _, _ in seen))

    def test_untrusted_cors_grant_is_failure(self):
        module = self.module()
        headers = {
            "Strict-Transport-Security": "max-age=1",
            "Content-Security-Policy": "default-src 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=()",
            "Access-Control-Allow-Origin": "https://security-probe.invalid",
        }
        def opener(request, timeout=0):
            path = __import__("urllib.parse").parse.urlsplit(request.full_url).path
            code = 200 if path == "/healthz" else 404 if path in {"/openapi.json", "/redoc"} else 401
            return FakeResponse(code, headers if path == "/healthz" else {})
        with self.assertRaises(module.ProbeFailure):
            module.run_probe("https://panel.example", opener=opener)

    def test_http_requires_explicit_loopback_override(self):
        module = self.module()
        with self.assertRaises(module.ProbeFailure):
            module.validate_base_url("http://panel.example", allow_http_loopback=False)
        with self.assertRaises(module.ProbeFailure):
            module.validate_base_url("http://192.0.2.10:19001", allow_http_loopback=True)
        self.assertEqual(
            module.validate_base_url("http://127.0.0.1:19001", allow_http_loopback=True),
            "http://127.0.0.1:19001",
        )

    def test_missing_security_header_is_failure(self):
        module = self.module()
        with self.assertRaises(module.ProbeFailure):
            module.check_security_headers({"X-Frame-Options": "DENY"})

    def test_sensitive_runtime_contracts_keep_private_modes(self):
        files = {
            "panel_settings": (ROOT / "backend/routers/panel_settings.py").read_text(),
            "runtime": (ROOT / "backend/panel_runtime_settings.py").read_text(),
            "backups": (ROOT / "backend/routers/backups.py").read_text(),
            "router": (ROOT / "scripts/pvnetwork-router-openvpn").read_text(),
            "installer": (ROOT / "scripts/install-runtime-tools.sh").read_text(),
        }
        self.assertIn("os.chmod(candidate_env, 0o600)", files["panel_settings"])
        self.assertIn("staging_dir.mkdir(parents=True, mode=0o700", files["panel_settings"])
        self.assertIn("os.chmod(temporary, 0o600)", files["backups"])
        self.assertIn("job_directory.mkdir(mode=0o700", files["backups"])
        self.assertIn("os.chmod(archive, 0o600)", files["backups"])
        self.assertIn("chmod(tmp,0o600)", files["router"])
        self.assertIn("pvnetwork-security-readonly-probe.py", files["installer"])


if __name__ == "__main__":
    unittest.main()
