import hashlib
import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pvnetwork-router-openvpn"
AUTH = Path(__file__).resolve().parents[1] / "scripts" / "pvnetwork-router-auth"


class RouterOpenVpnNodeHelperTests(unittest.TestCase):
    def _env(self, root: Path) -> dict:
        env = os.environ.copy()
        env.update({
            "PVNETWORK_ROUTER_OPENVPN_BASE": str(root / "etc/openvpn/server"),
            "PVNETWORK_ROUTER_STATE_DIR": str(root / "etc/pvnetwork/router-openvpn"),
            "PVNETWORK_ROUTER_HOME": str(root / "root"),
            "PVNETWORK_ROUTER_TEST_MODE": "1",
            "PVNETWORK_ROUTER_AUTH_SCRIPT": str(AUTH),
        })
        return env

    def _prepare(self, root: Path) -> Path:
        base = root / "etc/openvpn/server"
        (base / "easy-rsa/pki/issued").mkdir(parents=True)
        (base / "easy-rsa/pki/private").mkdir(parents=True)
        (base / "easy-rsa/pki").mkdir(parents=True, exist_ok=True)
        (root / "root").mkdir(parents=True)
        server = base / "server.conf"
        server.write_text("port 1194\nproto udp\n", encoding="utf-8")
        (base / "easy-rsa/pki/ca.crt").write_text("CA\n", encoding="utf-8")
        (base / "server.crt").write_text("SERVERCERT\n", encoding="utf-8")
        (base / "server.key").write_text("SERVERKEY\n", encoding="utf-8")
        return server

    def test_enable_never_rewrites_normal_server_conf(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            server = self._prepare(root)
            before = hashlib.sha256(server.read_bytes()).hexdigest()
            result = subprocess.run(
                [str(SCRIPT), "enable", "--port", "21195", "--subnet", "10.209.0.0/24", "--protocol", "tcp"],
                env=self._env(root), text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(before, hashlib.sha256(server.read_bytes()).hexdigest())
            secondary = root / "etc/openvpn/server/pvnetwork-router.conf"
            self.assertTrue(secondary.is_file())
            text = secondary.read_text(encoding="utf-8")
            self.assertIn("auth-user-pass-verify", text)
            self.assertIn("verify-client-cert require", text)
            self.assertNotIn("username-as-common-name", text)
            self.assertNotIn("user nobody", text)
            self.assertNotIn("group nogroup", text)
            credential_file = root / "etc/pvnetwork/router-openvpn/credentials.tsv"
            self.assertEqual(credential_file.stat().st_mode & 0o777, 0o600)

    def test_preflight_rejects_occupied_port_without_writes(self):
        with tempfile.TemporaryDirectory() as td, socket.socket() as sock:
            root = Path(td)
            self._prepare(root)
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            result = subprocess.run(
                [str(SCRIPT), "preflight", "--port", str(port), "--subnet", "10.209.0.0/24", "--protocol", "tcp"],
                env=self._env(root), text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "etc/openvpn/server/pvnetwork-router.conf").exists())

    def test_preflight_rejects_overlap_with_normal_server_subnet(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            server = self._prepare(root)
            server.write_text("port 1194\nproto udp\nserver 10.8.0.0 255.255.255.0\n", encoding="utf-8")
            result = subprocess.run(
                [str(SCRIPT), "preflight", "--port", "21195", "--subnet", "10.8.0.128/25", "--protocol", "tcp"],
                env=self._env(root), text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SUBNET", (result.stdout + result.stderr).upper())

    def test_node_patch_exposes_router_api_without_mutating_normal_config(self):
        import scripts.node_patch as node_patch

        for marker in (
            '@router.get("/router-openvpn/status")',
            '@router.post("/router-openvpn/preflight")',
            '@router.put("/router-openvpn/config")',
            '@router.put("/router-openvpn/credential")',
            '@router.get("/router-openvpn/profile/{cn}")',
        ):
            self.assertIn(marker, node_patch.ROUTER)
        source = Path(node_patch.__file__).read_text(encoding="utf-8")
        self.assertNotIn('ensure_line(server_conf', source)

    def test_auth_verifier_requires_matching_password_and_certificate_cn(self):
        from backend.router_openvpn.credentials import hash_router_password
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "state"
            state.mkdir()
            verifier = hash_router_password("Correct-Horse-Battery-Staple")
            (state / "credentials.tsv").write_text(
                f"router_1\tclient-cn\t1\t{verifier}\n",
                encoding="utf-8",
            )
            auth_file = root / "auth.txt"
            auth_file.write_text("router_1\nCorrect-Horse-Battery-Staple\n", encoding="utf-8")
            env = os.environ.copy()
            env["PVNETWORK_ROUTER_CREDENTIAL_FILE"] = str(state / "credentials.tsv")
            env["common_name"] = "client-cn"
            good = subprocess.run([str(AUTH), str(auth_file)], env=env)
            self.assertEqual(good.returncode, 0)
            env["common_name"] = "other-cn"
            wrong_cn = subprocess.run([str(AUTH), str(auth_file)], env=env)
            self.assertNotEqual(wrong_cn.returncode, 0)
            auth_file.write_text("router_1\nwrong-password\n", encoding="utf-8")
            env["common_name"] = "client-cn"
            wrong_password = subprocess.run([str(AUTH), str(auth_file)], env=env)
            self.assertNotEqual(wrong_password.returncode, 0)


if __name__ == "__main__":
    unittest.main()
