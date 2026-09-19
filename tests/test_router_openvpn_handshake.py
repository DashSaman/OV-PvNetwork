import subprocess
import unittest
from pathlib import Path


class RouterOpenVpnHandshakeContractTests(unittest.TestCase):
    def test_real_dual_auth_harness(self):
        harness = Path(__file__).resolve().parents[1] / "tests" / "router_openvpn_real_handshake.sh"
        self.assertTrue(harness.is_file())
        text = harness.read_text(encoding="utf-8")
        self.assertIn("wrong-password", text)
        self.assertIn("wrong-cn", text)
        self.assertIn("normal-listener", text)
        result = subprocess.run(
            ["bash", str(harness)],
            cwd=harness.parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-12000:])
        self.assertIn("REAL_DUAL_AUTH_HANDSHAKE=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
