from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.node.deploy import router_capability_install_script
import scripts.node_patch as node_patch

ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "scripts/node_patch.py"


class NodeUserLifecycleNoRestartTests(unittest.TestCase):
    def test_existing_node_upgrade_installs_user_lifecycle_patch(self):
        script = router_capability_install_script("/opt/ov-node")
        self.assertIn("--user-lifecycle-only", script)
        self.assertIn("core/service/user_managment.py", script)

    def test_patcher_supports_user_lifecycle_only_without_touching_router(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = root / "core/service"
            routers = root / "core/routers"
            service.mkdir(parents=True)
            routers.mkdir(parents=True)
            user_file = service / "user_managment.py"
            router_file = routers / "router.py"
            user_file.write_text(
                "import os\nimport re\nimport subprocess\n\n"
                "def create_user_on_server(name):\n    return True\n\n"
                "def delete_user_on_server(name):\n    return True\n\n"
                "def change_user_status(name, status):\n"
                "    os.system('systemctl restart openvpn-server@server')\n    return True\n\n"
                "def restart_openvpn_service():\n"
                "    os.system('systemctl restart openvpn-server@server')\n    return True\n\n"
                "async def download_ovpn_file(name):\n    return None\n",
                encoding="utf-8",
            )
            original_router = "router = object()\n"
            router_file.write_text(original_router, encoding="utf-8")
            result = subprocess.run(
                ["python3", str(PATCHER), str(root), "--user-lifecycle-only"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            patched = user_file.read_text(encoding="utf-8")
            self.assertEqual(router_file.read_text(encoding="utf-8"), original_router)
            self.assertIn("/run/openvpn/ov-management.sock", patched)
            self.assertIn("/var/run/openvpn-server/server.sock", patched)
            self.assertIn("_pvnetwork_disconnect(name)", patched)
            self.assertIn('"revoke", name', patched)
            self.assertIn('"gen-crl"', patched)
            lifecycle = patched[patched.index("def delete_user_on_server"):patched.index("async def download_ovpn_file")]
            self.assertNotIn("systemctl restart", lifecycle)
            self.assertNotIn("restart_openvpn_service()", lifecycle.replace("def restart_openvpn_service()", ""))


    def test_lifecycle_behaves_per_user_without_service_restart(self):
        class Logger:
            def info(self, *args, **kwargs): pass
            def error(self, *args, **kwargs): pass

        class Result:
            returncode = 0
            stdout = "ok"

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ccd = root / "ccd"
            easy = root / "easy-rsa"
            pki = easy / "pki"
            ccd.mkdir()
            pki.mkdir(parents=True)
            easyrsa = easy / "easyrsa"
            easyrsa.write_text("#!/bin/sh\n", encoding="utf-8")
            (pki / "index.txt").write_text("V\t351231000000Z\t\t01\tunknown\t/CN=alice\n", encoding="utf-8")
            (pki / "crl.pem").write_text("NEW-CRL\n", encoding="utf-8")
            for relative in ("issued/alice.crt", "private/alice.key", "reqs/alice.req", "inline/private/alice.inline"):
                artifact = pki / relative
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text("STALE\n", encoding="utf-8")
            crl_target = root / "crl.pem"
            crl_target.write_text("OLD-CRL\n", encoding="utf-8")
            mgmt = root / "ov-management.sock"
            mgmt.touch()
            server_conf = root / "server.conf"
            server_conf.write_text(
                f"client-config-dir {ccd}\ncrl-verify {crl_target}\n",
                encoding="utf-8",
            )
            calls = []
            def fake_run(args, **kwargs):
                calls.append((list(args), kwargs.get("input")))
                return Result()
            env = {
                "PVNETWORK_OPENVPN_SERVER_CONF": str(server_conf),
                "PVNETWORK_EASYRSA_DIR": str(easy),
                "PVNETWORK_OPENVPN_MANAGEMENT_SOCKET": str(mgmt),
            }
            ns = {
                "os": os,
                "re": re,
                "subprocess": subprocess,
                "logger": Logger(),
                "_safe_name": lambda name: bool(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(name or ""))),
            }
            with patch.dict(os.environ, env, clear=False):
                exec(node_patch.USER_LIFECYCLE_NO_RESTART, ns)
            (ccd / "alice").touch()
            with patch.object(subprocess, "run", side_effect=fake_run):
                self.assertTrue(ns["change_user_status"]("alice", "deactivate"))
                self.assertFalse((ccd / "alice").exists())
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][0][0], "socat")
                self.assertEqual(calls[0][1], "kill alice\nquit\n")
                calls.clear()
                self.assertTrue(ns["change_user_status"]("alice", "activate"))
                self.assertTrue((ccd / "alice").exists())
                self.assertEqual(calls, [])
                result = ns["delete_user_on_server"]("alice")
            self.assertIs(result, True)
            command_words = [call[0] for call in calls]
            self.assertTrue(any(cmd[0] == "socat" and payload == "kill alice\nquit\n" for cmd, payload in calls))
            self.assertTrue(any("revoke" in cmd and "alice" in cmd for cmd in command_words))
            self.assertTrue(any("gen-crl" in cmd for cmd in command_words))
            self.assertEqual(crl_target.read_text(encoding="utf-8"), "NEW-CRL\n")
            for relative in ("issued/alice.crt", "private/alice.key", "reqs/alice.req", "inline/private/alice.inline"):
                self.assertFalse((pki / relative).exists(), relative)
            self.assertFalse(any(cmd[:2] == ["systemctl", "restart"] for cmd in command_words))

    def test_certificate_lookup_matches_exact_cn_only(self):
        class Logger:
            def info(self, *args, **kwargs): pass
            def error(self, *args, **kwargs): pass
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            easy = root / "easy-rsa"
            pki = easy / "pki"
            pki.mkdir(parents=True)
            (pki / "index.txt").write_text(
                "V\t351231000000Z\t\t01\tunknown\t/CN=alice2\n",
                encoding="utf-8",
            )
            env = {"PVNETWORK_EASYRSA_DIR": str(easy)}
            ns = {
                "os": os, "re": re, "subprocess": subprocess, "logger": Logger(),
                "_safe_name": lambda name: True,
            }
            with patch.dict(os.environ, env, clear=False):
                exec(node_patch.USER_LIFECYCLE_NO_RESTART, ns)
            self.assertFalse(ns["_pvnetwork_valid_cert_exists"]("alice"))
            self.assertTrue(ns["_pvnetwork_valid_cert_exists"]("alice2"))

    def test_user_lifecycle_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = root / "core/service"
            routers = root / "core/routers"
            service.mkdir(parents=True)
            routers.mkdir(parents=True)
            user_file = service / "user_managment.py"
            router_file = routers / "router.py"
            user_file.write_text(
                "import os\nimport re\nimport subprocess\n\n"
                "def create_user_on_server(name):\n    return True\n\n"
                "def delete_user_on_server(name):\n    return True\n\n"
                "def change_user_status(name, status):\n    return True\n\n"
                "def restart_openvpn_service():\n    return True\n\n"
                "async def download_ovpn_file(name):\n    return None\n",
                encoding="utf-8",
            )
            router_file.write_text("router = object()\n", encoding="utf-8")
            cmd = ["python3", str(PATCHER), str(root), "--user-lifecycle-only"]
            first = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            once = user_file.read_text(encoding="utf-8")
            second = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(user_file.read_text(encoding="utf-8"), once)


if __name__ == "__main__":
    unittest.main()
