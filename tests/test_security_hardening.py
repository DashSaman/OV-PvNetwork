import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class SecurityHardeningContractTests(unittest.TestCase):
    def test_production_disables_openapi_and_redoc(self):
        app = text("backend/app.py")
        self.assertIn('openapi_url="/openapi.json" if config.DOC else None', app)
        self.assertIn('redoc_url="/redoc" if config.DOC else None', app)
        self.assertIn('@api.get("/healthz"', app)

    def test_main_admin_uses_hash_not_plaintext_comparison(self):
        auth = text("backend/auth/auth.py")
        env = text(".env.example")
        installer = text("install-local.sh")
        self.assertNotIn("password == main_admin_password", auth)
        self.assertIn("ADMIN_PASSWORD_HASH", auth)
        self.assertIn("ADMIN_PASSWORD_HASH=", env)
        self.assertNotIn("\nADMIN_PASSWORD=", env)
        self.assertIn("ADMIN_PASSWORD_HASH", installer)
        self.assertNotIn("ADMIN_PASSWORD=${ADMIN_PASS}", installer)

    def test_login_has_dedicated_throttle_and_security_headers(self):
        security = text("backend/security_middleware.py")
        app = text("backend/app.py")
        self.assertIn("LOGIN_RATE_LIMIT_PER_MINUTE", security)
        self.assertIn("/api/login", security)
        self.assertIn("SecurityHeadersMiddleware", security)
        self.assertIn("Strict-Transport-Security", security)
        self.assertIn("Content-Security-Policy", security)
        self.assertIn("SecurityHeadersMiddleware", app)

    def test_ssh_does_not_auto_trust_first_seen_keys(self):
        deploy = text("backend/node/deploy.py")
        fleet = text("backend/routers/fleet.py")
        node = text("backend/routers/node.py")
        self.assertNotIn("AutoAddPolicy", deploy)
        self.assertNotIn("AutoAddPolicy", fleet)
        self.assertIn("expected_fingerprint", deploy)
        self.assertIn("ssh_fingerprint", node)
        self.assertIn("ssh_fingerprint", fleet)

    def test_dependency_and_static_security_scans_are_release_gates(self):
        workflow = text(".github/workflows/ci.yml")
        pyproject = text("pyproject.toml").lower()
        self.assertIn("pip-audit", workflow)
        self.assertIn("bandit", workflow)
        self.assertNotIn("python-jose", pyproject)
        self.assertIn("pyjwt>=2.13", pyproject)
        self.assertIn("python-dotenv>=1.2.2", pyproject)

    def test_health_checks_do_not_depend_on_public_openapi(self):
        paths = [
            "install-local.sh",
            "scripts/healthcheck.sh",
            "scripts/manage.sh",
            "scripts/verify.sh",
            "scripts/pvnetwork-panel-restore-job",
        ]
        for path in paths:
            body = text(path)
            self.assertIn("/healthz", body, path)
            self.assertNotIn("/openapi.json", body, path)

    def test_firewall_hardening_is_inventory_first_and_reversible(self):
        body = text("scripts/pvnetwork-firewall-hardening")
        self.assertIn("--inventory", body)
        self.assertIn("--apply", body)
        self.assertIn("rollback", body.lower())
        self.assertIn("established,related", body.lower())


if __name__ == "__main__":
    unittest.main()
