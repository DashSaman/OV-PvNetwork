# PVNetwork Panel v1.0.8 — Production Security Hardening

**Patch task:** `PVN-028`

![v1.0.8 SSH host-key pinning field](./images/v1.0.8/en/desktop/ssh-host-key-pinning.png)

This release hardens the control plane without changing the default OpenVPN user experience. Existing certificate-based OpenVPN listeners, client certificates and profiles remain untouched.

## Security changes
- Main-admin authentication moves from a plaintext environment password to a one-way bcrypt hash, with a tested atomic migration path.
- Production API documentation/schema endpoints follow the `DOC` switch and a dedicated `/healthz` endpoint replaces documentation-based health probes.
- Login requests receive a tighter, isolated throttle; authenticated integration traffic keeps its existing path.
- Browser/API responses gain HSTS, frame, MIME, referrer, permissions and tested CSP headers.
- Automatic Node/Fleet SSH no longer trusts first-seen host keys. Unknown hosts require an explicitly verified fingerprint before they can be pinned.
- Runtime Python dependencies are upgraded as a tested set; `pip-audit` reports no known advisories and CI now blocks vulnerable dependency regressions.
- Bandit medium/high static-security findings are release-gated; reviewed fixed-command SSH calls are explicitly documented.
- A reversible inventory-first host firewall helper preserves existing tunnel/NFQUEUE rules, requires an explicit allowlist, snapshots rules first, and schedules automatic rollback unless the operator confirms health.

## Deployment safety
The panel is staged and verified on a parallel local canary before the canonical backend moves. The main-admin environment migration is backed up together with the application and PostgreSQL. Firewall enforcement is a separate final gate with timed rollback and is never allowed to change OpenVPN, Xray or tunnel configuration.

## OpenVPN remains unchanged
Normal users continue to use certificate-based `.ovpn` profiles without username/password prompts. Router/legacy username-password compatibility is a separate opt-in task and is not part of this release.
