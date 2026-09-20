import importlib.util
import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request
from starlette.responses import Response

os.environ.setdefault("ADMIN_USERNAME", "ci-admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "$2b$12$abcdefghijklmnopqrstuu1234567890123456789012")
os.environ.setdefault("MAIN_ADMIN_AUTH_GENERATION", "ci-generation")
os.environ.setdefault("JWT_SECRET_KEY", "ci-jwt-secret-not-production-32chars")

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "backend/panel_redirect.py"


def load_redirect(testcase):
    testcase.assertTrue(MODULE_PATH.exists(), "panel redirect middleware must exist")
    spec = importlib.util.spec_from_file_location("panel_redirect_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_once(module, method: str, target: str):
    path, _, query = target.partition("?")
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    request = Request(scope)
    middleware = module.PanelPathTransitionMiddleware(lambda scope, receive, send: None)

    async def call_next(_request):
        return Response(status_code=404)

    return asyncio.run(middleware.dispatch(request, call_next))


class PanelPathRedirectTests(unittest.TestCase):
    def test_old_path_redirects_before_expiry_with_suffix_and_query(self):
        module = load_redirect(self)
        state = {"old_path": "old", "new_path": "new", "redirect_expires_at": 1300, "change_id": "c1"}
        with patch.object(module, "load_transition_state", return_value=state), patch.object(module, "epoch_time", return_value=1000):
            response = request_once(module, "GET", "/old/users?tab=active")
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/new/users?tab=active")

    def test_old_path_is_not_redirected_at_expiry(self):
        module = load_redirect(self)
        state = {"old_path": "old", "new_path": "new", "redirect_expires_at": 1000, "change_id": "c1"}
        with patch.object(module, "load_transition_state", return_value=state), patch.object(module, "epoch_time", return_value=1000):
            response = request_once(module, "GET", "/old/users")
        self.assertEqual(response.status_code, 404)

    def test_redirect_preserves_asset_suffix_and_307_method_semantics(self):
        module = load_redirect(self)
        state = {"old_path": "old", "new_path": "new", "redirect_expires_at": 1300, "change_id": "c1"}
        with patch.object(module, "load_transition_state", return_value=state), patch.object(module, "epoch_time", return_value=1000):
            response = request_once(module, "POST", "/old/assets/app.js?x=1")
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/new/assets/app.js?x=1")

    def test_unrelated_and_server_owned_paths_never_redirect(self):
        module = load_redirect(self)
        state = {"old_path": "old", "new_path": "new", "redirect_expires_at": 1300, "change_id": "c1"}
        with patch.object(module, "load_transition_state", return_value=state), patch.object(module, "epoch_time", return_value=1000):
            for path in ["/api/users", "/healthz", "/sub/abc", "/oldish/users", "/new/users", "/other"]:
                with self.subTest(path=path):
                    response = request_once(module, "GET", path)
                    self.assertEqual(response.status_code, 404)

    def test_malformed_transition_state_is_ignored(self):
        module = load_redirect(self)
        states = [None, {}, {"old_path": "../old", "new_path": "new", "redirect_expires_at": 1300}, {"old_path": "old", "new_path": "https://evil", "redirect_expires_at": 1300}]
        for state in states:
            with self.subTest(state=state), patch.object(module, "load_transition_state", return_value=state), patch.object(module, "epoch_time", return_value=1000):
                response = request_once(module, "GET", "/old/users")
                self.assertEqual(response.status_code, 404)

    def test_application_registers_transition_middleware(self):
        module = load_redirect(self)
        self.assertTrue(hasattr(module, "PanelPathTransitionMiddleware"))
        source = (ROOT / "backend/app.py").read_text(encoding="utf-8")
        self.assertIn("PanelPathTransitionMiddleware", source)
        self.assertIn("api.add_middleware(PanelPathTransitionMiddleware)", source)


if __name__ == "__main__":
    unittest.main()
