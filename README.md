<div align="center">

# PVNetwork Panel

**Multi-node OpenVPN control plane with renewal, reseller, monitoring, automation and optional AnyConnect integration**

[![Version](https://img.shields.io/badge/version-1.0.0-green?style=flat-square)](./VERSION)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](./LICENSE)

**English** · [فارسی](./README.fa.md)

</div>

## Stable release

`v1.0.0` is the first frozen public stable baseline. The release source is generated from a sanitized production snapshot and intentionally contains no production credentials, IP addresses, hostnames, databases, customer data, VPN profiles, private keys or certificates.

## Quick install

Run as `root` on a fresh Ubuntu 22.04/24.04 or Debian 12 server:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/DashSaman/OV-PvNetwork/main/install.sh)
```

The bootstrap downloads the `v1.0.0` release asset, verifies its SHA-256 checksum and runs the local installer. Existing `/opt/ov-panel` installations are not overwritten by the fresh installer.

## Main capabilities

- Multi-node OpenVPN user and node management.
- Automatic node deployment over SSH from Node Management.
- Per-user node assignment and global concurrent-session limits.
- Traffic quota, unlimited plans, expiry and first-class renewal.
- Unlimited Reset Usage starts a new 30-day period while preserving the same account identity.
- Self-healing OpenVPN profile validation/rebuild on download.
- Optional AnyConnect per user.
- Live node CPU, RAM, uptime, network traffic and health monitoring.
- Node drain, maintenance, weight, fleet operations, canary and rollback foundations.
- Reseller traffic/unlimited-account quotas and credit ledger.
- Bulk user operations and automatic rebalance workflows.
- Emergency bandwidth policies with fail-open/rollback behavior.
- Audit log, API tokens, rate limiting, IP allow-list and TOTP/2FA support.
- Backup/restore and operational health controls.
- Usage history and domain-activity reporting.
- Telegram monitoring hooks and Mirza integration APIs.
- Branded multilingual subscription page, client downloads, smart node recommendation and Web Push reminders.

See [docs/FEATURES.md](./docs/FEATURES.md) and [docs/FEATURE-MATRIX.md](./docs/FEATURE-MATRIX.md).

## Adding VPN nodes

After the panel is installed:

1. Open **Node Management**.
2. Choose **Add Node**.
3. Select automatic SSH deployment.
4. Enter the target server connection details in the panel.
5. The panel installs and validates the node, OpenVPN integration and management API without requiring a separate public credential file.

See [docs/NODE-INSTALLATION.md](./docs/NODE-INSTALLATION.md).

## Public repository privacy rule

Never commit real deployment values. Keep these only on the live server or in a private operations store:

- `.env` and generated credentials
- admin/Mirza/API/JWT secrets
- SSH credentials and node API keys
- real infrastructure IP addresses, domains and private routes
- databases, logs and customer identifiers
- `.ovpn`, private keys, TLS/VAPID keys and certificates

The stable release is scanned before publication. See `SECRET-SCAN-REPORT.md` in the release source archive.

## Release policy

The `v1.0.0` baseline is frozen. New work is released separately:

- `1.0.x` — compatible bug/security fixes
- `1.x.0` — backward-compatible features
- `2.0.0` — breaking architecture/protocol changes

Production services are never used as a development workspace for a future release. Changes are prepared/tested separately, then deployed with backup and health verification.

See [docs/RELEASE-POLICY.md](./docs/RELEASE-POLICY.md).

## Credits

PVNetwork Panel is derived from and interoperates with the MIT-licensed OV-Panel and OV-Node projects by PrimeZ. Upstream attribution remains in [NOTICE.md](./NOTICE.md) and [LICENSE](./LICENSE).
