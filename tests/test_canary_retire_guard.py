from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pvnetwork-canary-retire-guard.py"


def load_guard():
    if not SCRIPT.is_file():
        raise AssertionError("canary retire guard script is missing")
    spec = importlib.util.spec_from_file_location("pvn_canary_retire_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CanaryRetireGuardTests(unittest.TestCase):
    def test_rejects_nginx_site_still_pointing_to_canary(self):
        guard = load_guard()
        with self.assertRaisesRegex(RuntimeError, "canary.*19002"):
            guard.validate_proxy_targets("proxy_pass http://127.0.0.1:19002;", 19001, 19002)

    def test_accepts_canonical_only_proxy_target(self):
        guard = load_guard()
        targets = guard.validate_proxy_targets("proxy_pass http://127.0.0.1:19001;", 19001, 19002)
        self.assertEqual(targets, [19001])

    def test_rejects_when_canonical_proxy_is_missing(self):
        guard = load_guard()
        with self.assertRaisesRegex(RuntimeError, "canonical.*19001"):
            guard.validate_proxy_targets("proxy_pass http://127.0.0.1:18000;", 19001, 19002)

    def test_ignores_commented_proxy_pass(self):
        guard = load_guard()
        text = "# proxy_pass http://127.0.0.1:19002;\nproxy_pass http://127.0.0.1:19001;"
        self.assertEqual(guard.validate_proxy_targets(text, 19001, 19002), [19001])

    def test_retire_guard_requires_canonical_and_public_http_200(self):
        guard = load_guard()
        seen = []
        def fake_http(url):
            seen.append(url)
            return 200
        self.assertTrue(hasattr(guard, "guard_retirement"), "guard_retirement is missing")
        targets = guard.guard_retirement(
            "proxy_pass http://127.0.0.1:19001;",
            canonical_port=19001,
            canary_port=19002,
            canonical_url="http://127.0.0.1:19001/healthz",
            public_url="https://panel.example/healthz",
            http_status=fake_http,
        )
        self.assertEqual(targets, [19001])
        self.assertEqual(seen, ["http://127.0.0.1:19001/healthz", "https://panel.example/healthz"])

    def test_retire_guard_rejects_public_502(self):
        guard = load_guard()
        def fake_http(url):
            return 502 if url.startswith("https://") else 200
        self.assertTrue(hasattr(guard, "guard_retirement"), "guard_retirement is missing")
        with self.assertRaisesRegex(RuntimeError, "public.*502"):
            guard.guard_retirement(
                "proxy_pass http://127.0.0.1:19001;",
                canonical_port=19001,
                canary_port=19002,
                canonical_url="http://127.0.0.1:19001/healthz",
                public_url="https://panel.example/healthz",
                http_status=fake_http,
            )

    def test_retire_guard_rejects_canonical_health_failure(self):
        guard = load_guard()
        self.assertTrue(hasattr(guard, "guard_retirement"), "guard_retirement is missing")
        with self.assertRaisesRegex(RuntimeError, "canonical.*000"):
            guard.guard_retirement(
                "proxy_pass http://127.0.0.1:19001;",
                canonical_port=19001,
                canary_port=19002,
                canonical_url="http://127.0.0.1:19001/healthz",
                public_url="https://panel.example/healthz",
                http_status=lambda url: 0,
            )

    def test_nginx_syntax_guard_rejects_failed_check(self):
        guard = load_guard()
        class Result:
            returncode = 1
            stderr = "nginx config invalid"
        self.assertTrue(hasattr(guard, "require_nginx_syntax_ok"), "require_nginx_syntax_ok is missing")
        with self.assertRaisesRegex(RuntimeError, "nginx syntax"):
            guard.require_nginx_syntax_ok(run=lambda *a, **k: Result())

    def test_cli_reports_safe_only_after_all_checks_pass(self):
        guard = load_guard()
        self.assertTrue(hasattr(guard, "main"), "main is missing")
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "panel.conf"
            site.write_text("proxy_pass http://127.0.0.1:19001;\n", encoding="utf-8")
            out = io.StringIO()
            events = []
            def fake_http(url):
                events.append(url)
                return 200
            with contextlib.redirect_stdout(out):
                rc = guard.main(
                    ["--nginx-site", str(site), "--public-url", "https://panel.example/healthz"],
                    syntax_check=lambda: None,
                    reload_nginx=lambda: events.append("reload"),
                    http_get=fake_http,
                )
        self.assertEqual(rc, 0)
        self.assertIn("CANARY_RETIRE_SAFE=YES", out.getvalue())
        self.assertEqual(events[0], "reload")

    def test_cli_refuses_when_site_still_uses_canary(self):
        guard = load_guard()
        self.assertTrue(hasattr(guard, "main"), "main is missing")
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "panel.conf"
            site.write_text("proxy_pass http://127.0.0.1:19002;\n", encoding="utf-8")
            out = io.StringIO()
            reloads = []
            with contextlib.redirect_stdout(out):
                rc = guard.main(
                    ["--nginx-site", str(site), "--public-url", "https://panel.example/healthz"],
                    syntax_check=lambda: None,
                    reload_nginx=lambda: reloads.append("reload"),
                    http_get=lambda url: 200,
                )
        self.assertEqual(rc, 1)
        self.assertIn("CANARY_RETIRE_SAFE=NO", out.getvalue())
        self.assertEqual(reloads, [])

    def test_runtime_installer_installs_canary_retire_guard(self):
        installer = (ROOT / "scripts/install-runtime-tools.sh").read_text(encoding="utf-8")
        self.assertIn(
            'install -m 0755 "$ROOT/scripts/pvnetwork-canary-retire-guard.py" /usr/local/sbin/pvnetwork-canary-retire-guard',
            installer,
        )

    def test_cli_requires_nginx_site_argument(self):
        guard = load_guard()
        with self.assertRaises(SystemExit) as ctx:
            guard.main(
                ["--public-url", "https://panel.example/healthz"],
                syntax_check=lambda: None,
                http_get=lambda url: 200,
            )
        self.assertEqual(ctx.exception.code, 2)

    def test_cli_reload_failure_blocks_retirement(self):
        guard = load_guard()
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "panel.conf"
            site.write_text("proxy_pass http://127.0.0.1:19001;\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = guard.main(
                    ["--nginx-site", str(site), "--public-url", "https://panel.example/healthz"],
                    syntax_check=lambda: None,
                    reload_nginx=lambda: (_ for _ in ()).throw(RuntimeError("reload failed")),
                    http_get=lambda url: 200,
                )
        self.assertEqual(rc, 1)
        self.assertIn("CANARY_RETIRE_SAFE=NO", out.getvalue())
        self.assertIn("reload failed", out.getvalue())


if __name__ == "__main__":
    unittest.main()
