import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.node.requests import NodeRequests
import scripts.node_patch as node_patch


class _Response:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)
    def json(self):
        return self._data


class RenameNodeContractTests(unittest.TestCase):
    def test_node_requests_identity_payload_is_sanitized_and_normalized(self):
        raw = {"success": True, "data": {
            "exists": 1, "valid_certificate": True, "profile_exists": 1,
            "ccd_enabled": 0, "connected": False, "client_name": "ali-NodeA",
            "capability_version": "pvn-user-identity-v1", "private_key": "NO", "path": "/secret",
        }}
        client = NodeRequests("127.0.0.1", 8080, "1234567890")
        self.assertTrue(hasattr(client, "get_user_identity"), "NodeRequests.get_user_identity missing")
        with patch("backend.node.requests.requests.get", return_value=_Response(raw)):
            payload = client.get_user_identity("ali-NodeA")
        self.assertEqual(set(payload), {"exists", "valid_certificate", "profile_exists", "ccd_enabled", "connected", "client_name", "capability_version"})
        self.assertTrue(payload["exists"])
        self.assertEqual(payload["client_name"], "ali-NodeA")
        self.assertNotIn("private", json.dumps(payload).lower())

    def test_patched_node_exposes_identity_route(self):
        source = node_patch.ROUTER
        self.assertIn('"/user/{name}/identity"', source)
        self.assertIn("get_user_identity_state", source)

    def test_identity_inspection_is_exact_cn_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            easy = root / "easy-rsa"; (easy / "pki").mkdir(parents=True)
            (easy / "pki" / "index.txt").write_text("V\t\t\t\t\t/CN=ali-NodeA\n")
            status = root / "status.log"
            status.write_text("CLIENT_LIST,ali2-NodeA,10.0.0.2:1,10.8.0.2,1,1\n")
            profiles = root / "profiles"; profiles.mkdir()
            old = dict(os.environ)
            try:
                os.environ["PVNETWORK_EASYRSA_DIR"] = str(easy)
                os.environ["PVNETWORK_OPENVPN_STATUS_LOG"] = str(status)
                os.environ["PVNETWORK_PROFILE_DIR"] = str(profiles)
                ns = {"logger": type("L", (), {"error": lambda *a, **k: None, "info": lambda *a, **k: None})()}
                exec(node_patch.USER_LIFECYCLE_NO_RESTART, ns)
                self.assertIn("get_user_identity_state", ns, "identity helper missing")
                state = ns["get_user_identity_state"]("ali-NodeA")
            finally:
                os.environ.clear(); os.environ.update(old)
            self.assertEqual(state["client_name"], "ali-NodeA")
            self.assertTrue(state["valid_certificate"])
            self.assertFalse(state["connected"])

    def test_router_only_upgrades_legacy_router_with_identity_contract_idempotently(self):
        legacy = node_patch.ROUTER.replace("    get_user_identity_state,\n", "")
        # Production legacy OV-Node has no trailing comma on the last import.
        legacy = legacy.replace("    get_users_usage,\n", "    get_users_usage\n")
        start = legacy.index('@router.get("/user/{name}/identity"')
        end = legacy.index('@router.delete("/user/{name}"', start)
        legacy = legacy[:start] + legacy[end:]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            routers = root / "core" / "routers"
            routers.mkdir(parents=True)
            (routers / "router.py").write_text(legacy)
            node_patch.install_router_openvpn_module(root)
            first = (routers / "router.py").read_text()
            try:
                compile(first, "router.py", "exec")
            except SyntaxError as exc:
                self.fail(f"patched legacy router must compile: {exc}")
            self.assertIn("get_user_identity_state", first)
            self.assertIn('"/user/{name}/identity"', first)
            node_patch.install_router_openvpn_module(root)
            second = (routers / "router.py").read_text()
            self.assertEqual(first, second)

    def test_lifecycle_patch_contains_no_real_openvpn_restart(self):
        body = node_patch.USER_LIFECYCLE_NO_RESTART.lower()
        self.assertNotIn("systemctl restart openvpn", body)
        self.assertNotIn("systemctl restart openvpn-server", body)


if __name__ == "__main__":
    unittest.main()
