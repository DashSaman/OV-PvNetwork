import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import paramiko

from backend import security_ssh


class SecuritySshTests(unittest.TestCase):
    def setUp(self):
        self.key = paramiko.RSAKey.generate(1024)
        self.fingerprint = security_ssh.sha256_fingerprint(self.key)

    def test_unknown_host_without_pin_is_rejected(self):
        policy = security_ssh.PinnedHostKeyPolicy()
        client = paramiko.SSHClient()
        with self.assertRaises(paramiko.SSHException):
            policy.missing_host_key(client, "node.example", self.key)

    def test_wrong_pin_is_rejected(self):
        policy = security_ssh.PinnedHostKeyPolicy(
            "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        client = paramiko.SSHClient()
        with self.assertRaises(paramiko.SSHException):
            policy.missing_host_key(client, "node.example", self.key)

    def test_matching_pin_is_accepted_and_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            known_hosts = Path(tmp) / "known_hosts"
            policy = security_ssh.PinnedHostKeyPolicy(self.fingerprint)
            client = paramiko.SSHClient()
            with patch.object(security_ssh, "KNOWN_HOSTS_PATH", known_hosts):
                policy.missing_host_key(client, "node.example", self.key)
            self.assertTrue(known_hosts.is_file())
            self.assertEqual(known_hosts.stat().st_mode & 0o777, 0o600)
            loaded = paramiko.HostKeys(str(known_hosts))
            self.assertIn("node.example", loaded)

    def test_fingerprint_helpers_match_sha256_and_md5(self):
        self.assertTrue(
            security_ssh.fingerprint_matches(self.key, self.fingerprint)
        )
        md5 = security_ssh.md5_fingerprint(self.key)
        self.assertTrue(security_ssh.fingerprint_matches(self.key, md5))
        self.assertTrue(security_ssh.fingerprint_matches(self.key, f"MD5:{md5}"))


if __name__ == "__main__":
    unittest.main()
