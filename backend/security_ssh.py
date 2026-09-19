from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

import paramiko

KNOWN_HOSTS_PATH = Path(
    os.getenv(
        "PVNETWORK_SSH_KNOWN_HOSTS",
        "/opt/pvnetwork-panel/data/ssh_known_hosts",
    )
)


def sha256_fingerprint(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    encoded = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{encoded}"


def md5_fingerprint(key: paramiko.PKey) -> str:
    return ":".join(f"{byte:02x}" for byte in key.get_fingerprint())


def fingerprint_matches(key: paramiko.PKey, expected: str | None) -> bool:
    value = str(expected or "").strip()
    if not value:
        return False
    if value.upper().startswith("SHA256:"):
        return value == sha256_fingerprint(key)
    normalized = value.lower().replace("md5:", "")
    return normalized == md5_fingerprint(key)


class PinnedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Reject unknown SSH hosts unless an explicit fingerprint matches."""

    def __init__(self, expected_fingerprint: str | None = None):
        self.expected_fingerprint = (
            str(expected_fingerprint or "").strip() or None
        )

    def missing_host_key(self, client, hostname, key):
        observed = sha256_fingerprint(key)
        if not self.expected_fingerprint:
            raise paramiko.SSHException(
                f"Unknown SSH host key for {hostname}. "
                f"Observed fingerprint: {observed}. Verify it and retry."
            )
        if not fingerprint_matches(key, self.expected_fingerprint):
            raise paramiko.SSHException(
                f"SSH host key mismatch for {hostname}. "
                f"Observed fingerprint: {observed}."
            )

        client._host_keys.add(hostname, key.get_name(), key)
        KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            if KNOWN_HOSTS_PATH.exists():
                existing = paramiko.HostKeys(str(KNOWN_HOSTS_PATH))
            else:
                existing = paramiko.HostKeys()
            existing.add(hostname, key.get_name(), key)
            existing.save(str(KNOWN_HOSTS_PATH))
            os.chmod(KNOWN_HOSTS_PATH, 0o600)
        except OSError:
            pass


def configure_ssh_client(
    client: paramiko.SSHClient,
    *,
    expected_fingerprint: str | None = None,
) -> None:
    client.load_system_host_keys()
    if KNOWN_HOSTS_PATH.exists():
        client.load_host_keys(str(KNOWN_HOSTS_PATH))
    client.set_missing_host_key_policy(
        PinnedHostKeyPolicy(expected_fingerprint)
    )
